#!/usr/bin/python3

import os, stat
import os, subprocess, logging, argparse

import mtp

logger = logging.getLogger(__name__)

class Directory(object):
    def __init__(self, path):
        object.__setattr__(self, 'path', path)

    def __setattr__(self, key, value):
        path = object.__getattribute__(self, 'path')
        if type(value) == str:
            with open(os.path.join(path, key), 'w') as k:
                k.write(value)
        elif type(value) == Directory:
            try:
                os.symlink(object.__getattribute__(value, 'path'), os.path.join(path, key))
            except FileExistsError:
                os.unlink(os.path.join(path, key))
                os.symlink(object.__getattribute__(value, 'path'), os.path.join(path, key))
        elif value is None:
            os.makedirs(os.path.join(path, key))

    def __getattribute__(self, key):
        path = object.__getattribute__(self, 'path')
        attr = os.path.join(path, key)
        try:
            mode = os.stat(attr)[stat.ST_MODE]
            if stat.S_ISDIR(mode):
                return Directory(attr)
            elif stat.S_ISREG(mode):
                with open(attr, 'r') as f:
                    value = f.read()
                return value
        except FileNotFoundError:
            return NotExist(attr)

    def __delattr__(self, key):
        path = object.__getattribute__(self, 'path')
        attr = os.path.join(path, key)
        mode = os.lstat(attr)[stat.ST_MODE]
        if stat.S_ISDIR(mode):
            os.rmdir(attr)
        else:
            os.unlink(attr)

    def __getitem__(self, key):
        return type(self).__getattribute__(self, key)

    def __setitem__(self, key, value):
        return type(self).__setattr__(self, key, value)

    def __delitem__(self, key):
        return type(self).__delattr__(self, key)


class NotExist(Directory):

    def __setattr__(self, key, value):
        path = object.__getattribute__(self, 'path')
        os.makedirs(path, exist_ok=True)
        Directory.__setattr__(self, key, value)




CONFIGDIR = '/sys/kernel/config/usb_gadget/'
#CONFIGDIR = '/tmp/cfs/'

class Gadget(object):
    def __init__(self, name, vid, pid, manufacturer, product, serialnumber):
        self.name = name
        self.vid = vid
        self.pid = pid
        self.manufacturer = manufacturer
        self.product = product
        self.serialnumber = serialnumber
        self.gadget = Directory(CONFIGDIR)[self.name]

    def add_function(self, function, config):
        if type(self.gadget.functions[function]) == NotExist:
            self.gadget.functions[function] = None
        self.gadget.configs[config][function] = self.gadget.functions[function]

    def remove_function(self, function, config):
        del self.gadget.configs[config][function]

    def bind(self, udc):
        logger.info('Binding to {}'.format(udc))
        self.gadget.UDC = udc

    def remove_gadget(self):
        del Directory(CONFIGDIR)[self.name]

class XGadget(Gadget):

    def __enter__(self):
        print('Configuring gadget')
        self.gadget.bcdUSB = '0x0200' # 2
        self.gadget.bDeviceClass = '0xff'
        self.gadget.bDeviceSubClass = '0xff'
        self.gadget.bDeviceProtocol = '0xff'
        self.gadget.bMaxPacketSize0 = 8
        self.gadget.bcdDevice = '0x0110' # 1.10
        self.gadget.idVendor = '0x0079' #'0x045e' # self.vid
        self.gadget.idProduct = '0x18d2'#'0x028e' # self.pid

        # os desciptor (example)
        self.gadget.os_desc.use = '1'
        self.gadget.os_desc.b_vendor_code = '0xcd'
        self.gadget.os_desc.qw_sign = 'MSFT100'

        self.gadget.strings['0x409'].serialnumber = '3' # self.serialnumber
        self.gadget.strings['0x409'].manufacturer = '1' # self.manufacturer
        self.gadget.strings['0x409'].product = 'AsoPi XBox 360 C' # self.product (this will be shown when using mtp)

        # rndis os desc strings example (if providing rndis functionality)
        #self.gadget.functions['rndis.usb0'].os_desc['interface.rndis'].compatible_id = 'RNDIS'
        #self.gadget.functions['rndis.usb0'].os_desc['interface.rndis'].sub_compatible_id = '5162001'

        self.gadget.configs['c.1'].strings['0x409'].configuration = 'X'

        # other function combinations:
        #   'rndis.usb0', 'acm.GS0', 'acm.GS1', etc.
        # TODO: for composite devices, save these in a list
        self.fn_name, self.inst_name = 'ffs', 'ocharley' # function name, instance name
        # fn_name = one of allowed function names (ffs, hid, acm, rndis, etc.)
        # inst_name = an arbitrary string allowed in a filesystem
        self.add_function('%s.%s' % (self.fn_name, self.inst_name), 'c.1')

        self.mount = '/dev/x360'
        print('making %s' % self.mount)
        os.makedirs(self.mount, exist_ok=True)

        # NOTE: 
        subprocess.call(['mount', '-c', '-t', 'functionfs', self.inst_name, self.mount])

        return self

    def __exit__(self, t, value, traceback):
        print('Tearing down gadget')
        self.gadget.UDC = ''

        if(subprocess.call(['umount', self.mount])):
            print('Unable to tear down gadget because functionfs is still in use.')
            return

        # cleanup any functions created above
        finns = '%s.%s' % (self.fn_name, self.inst_name)
        self.remove_function(finns, 'c.1')

        # clean up directories
        del self.gadget.configs['c.1'].strings['0x409']
        del self.gadget.configs['c.1']
        del self.gadget.functions[finns]
        del self.gadget.strings['0x409']

        self.remove_gadget()

import asyncio

import functionfs
import functionfs.ch9

from mtp.kaio import KAIOReader, KAIOWriter
from mtp.responder import MTPResponder

FS_BULK_MAX_PACKET_SIZE = 64
HS_BULK_MAX_PACKET_SIZE = 512

import io

import logging
logger = logging.getLogger(__name__)

from mtp.exceptions import MTPError
from mtp.device import DeviceInfo, DeviceProperties, DevicePropertyCode
from mtp.packets import MTPOperation, MTPResponse, DataFormats, OperationCode, EventCode
from mtp.watchmanager import WatchManager
from mtp.handlemanager import HandleManager
from mtp.storage import StorageManager, FilesystemStorage
from mtp.object import ObjectInfo, ObjectPropertyCode, ObjectPropertyCodeArray, ObjectPropertyDesc, builddesc
from mtp.registry import Registry

from construct import *
ContainerType = Enum(Int16ul, **dict(mtp.constants.container_types))
OperationCode = Enum(Int16ul, **dict(mtp.constants.operation_codes))
ResponseCode = Enum(Int16ul, **dict(mtp.constants.response_codes))
EventCode = Enum(Int16ul, **dict(mtp.constants.event_codes))

DataType = Enum(Int16ul, **{x[0]: x[1] for x in mtp.constants.data_types})
DataFormats = {x[0]: x[2] for x in mtp.constants.data_types}

MTPOperation = Struct(
    'length' / Int32ul,
    'type' / Const('OPERATION', ContainerType),
    'code' / OperationCode,
    'tx_id' / Int32ul,
    'p1' / Default(Int32ul, 0), 
    'p2' / Default(Int32ul, 0), 
    'p3' / Default(Int32ul, 0), 
    'p4' / Default(Int32ul, 0), 
    'p5' / Default(Int32ul, 0), 
)

import struct
from collections import namedtuple
XReport = namedtuple('XReport', 'type bset1 bset2 rt lt x y z r')
msgfmt = 'xBBBBBHHHH4x2x'
msg = [ # neutral(?)
    # 0, dummy
    0x14, # type, length (const)
    0, 0, # bset1 (incl. hat), bset2
    0, 0, # rt, lt
    00, 00, # x, y
    00, 00, # z, r
    # 0000, 00, # dummy (const)
]

# TODO: first connect messages:
# On first connect the controller sends:

# len: 3 data: 0x01 0x03 0x0e // current LED status
# len: 3 data: 0x02 0x03 0x00 // UNKNOWN: maybe headset connection status or volume
# len: 3 data: 0x03 0x03 0x03 // Rumble Status (0x00 in the last pos means rumble is disabled, 0x03 is default)
# len: 3 data: 0x08 0x03 0x00 // Headset connection status (0x00 no headset, 0x02 headset)
#                             // also chatpad status, but requires sending 0x1f before its reported
# len: 20 data: 0x00 0x14 0x00 0x00 0x00 0x00 0x69 0xed 0x23 0xff 0x6b 0x00 0x15 0x03 0x00 0x00 0x00 0x00 0x00 0x00 
# len: 20 data: 0x00 0x14 0x00 0x00 0x00 0x00 0xfc 0xec 0x23 0xff 0x6b 0x00 0x15 0x03 0x00 0x00 0x00 0x00 0x00 0x00 
# (20s are controller state reports)
'''
struct Xbox360Msg
{
  // -------------------------
  unsigned int type       :8; // always 0
  unsigned int length     :8; // always 0x14 

  // data[2] ------------------
  unsigned int dpad_up     :1;
  unsigned int dpad_down   :1;
  unsigned int dpad_left   :1;
  unsigned int dpad_right  :1;

  unsigned int start       :1;
  unsigned int back        :1;

  unsigned int thumb_l     :1;
  unsigned int thumb_r     :1;

  // data[3] ------------------
  unsigned int lb          :1;
  unsigned int rb          :1;
  unsigned int guide       :1;
  unsigned int dummy1      :1; // always 0

  unsigned int a           :1; // green
  unsigned int b           :1; // red
  unsigned int x           :1; // blue
  unsigned int y           :1; // yellow

  // data[4] ------------------
  unsigned int lt          :8;
  unsigned int rt          :8;

  // data[6] ------------------
  int x1                   :16;
  int y1                   :16;

  // data[10] -----------------
  int x2                   :16;
  int y2                   :16;

  // data[14]; ----------------
  unsigned int dummy2      :32; // always 0
  unsigned int dummy3      :16; // always 0
} __attribute__((__packed__));
'''
class MTPResponder(object):
    operations = Registry()

    def __init__(self, outep, inep, intep, loop, args):
        self.outep = outep
        self.inep = inep
        self.intep = intep
        self.loop = loop
        self.loop.add_reader(self.outep, self.handleOneOperation)
        self.loop.add_reader(self.intep, self.intep.pump)

        self.session_id = None
        self.properties = DeviceProperties(
            ('DEVICE_FRIENDLY_NAME', args.name),
            ('SYNCHRONIZATION_PARTNER', '', True),
        )

        self.object_info = None

        self.eventqueue = []
        self.wm = WatchManager()
        self.hm = HandleManager()
        self.sm = StorageManager(self.hm)

        for s in args.storage:
            FilesystemStorage(s[0], s[1], self.sm, self.hm, self.wm)

        self.loop.add_reader(self.wm, self.wm.dispatch)
# len: 3 data: 0x01 0x03 0x0e // current LED status
# len: 3 data: 0x02 0x03 0x00 // UNKNOWN: maybe headset connection status or volume
# len: 3 data: 0x03 0x03 0x03 // Rumble Status (0x00 in the last pos means rumble is disabled, 0x03 is default)
# len: 3 data: 0x08 0x03 0x00 // Headset connection status (0x00 no headset, 0x02 headset)
#                             // also chatpad status, but requires sending 0x1f before its reported
# len: 20 data: 0x00 0x14 0x00 0x00 0x00 0x00 0x69 0xed 0x23 0xff 0x6b 0x00 0x15 0x03 0x00 0x00 0x00 0x00 0x00 0x00 
# len: 20 data: 0x00 0x14 0x00 0x00 0x00 0x00 0xfc 0xec 0x23 0xff 0x6b 0x00 0x15 0x03 0x00 0x00 0x00 0x00 0x00 0x00 
        #self.inep.write(bytes([0x01,0x03,0x0e]))
        #self.inep.write(bytes([0x02,0x03,0x00]))
        #self.inep.write(bytes([0x03,0x03,0x03]))
        #self.inep.write(bytes([0x08,0x03,0x00]))

    @operations.sender
    def GET_DEVICE_INFO(self, p):
        data = DeviceInfo.build(dict(
                 device_properties_supported=self.properties.supported(),
                 operations_supported=sorted(self.operations.keys(), key=lambda o: OperationCode.encmapping[o]),
                 events_supported=sorted([
                     'OBJECT_ADDED',
                     'OBJECT_REMOVED',
                     'OBJECT_INFO_CHANGED',
                     'STORE_ADDED',
                     'STORE_REMOVED',
                     'STORAGE_INFO_CHANGED',
                     'STORE_FULL',
                     'DEVICE_INFO_CHANGED',
                     'DEVICE_RESET',
                     'UNREPORTED_STATUS',
                 ], key=lambda e: EventCode.encmapping[e])
               ))
        return (io.BytesIO(data), ())

    @operations
    def OPEN_SESSION(self, p):
        if self.session_id is not None:
            raise MTPError('SESSION_ALREADY_OPEN', (self.session_id,))
        else:
            self.session_id = p.p1
        logger.info('Session opened.')
        return (self.session_id,)

    @operations.session
    def CLOSE_SESSION(self, p):
        self.session_id = None
        logger.info('Session closed.')
        return ()

    @operations.sender
    def GET_STORAGE_IDS(self, p):
        data = DataFormats['AUINT32'].build(list(self.sm.ids()))
        return (io.BytesIO(data), ())

    @operations.sender
    def GET_STORAGE_INFO(self, p):
        data = self.sm[p.p1].build()
        return (io.BytesIO(data), ())

    @operations.session
    def GET_NUM_OBJECTS(self, p):
        if p.p2 != 0:
            raise MTPError('SPECIFICATION_BY_FORMAT_UNSUPPORTED')
        else:
            num = len(self.sm.handles(p.p1, p.p3))
        return (num, )

    @operations.sender
    def GET_OBJECT_HANDLES(self, p):
        if p.p2 != 0:
            raise MTPError('SPECIFICATION_BY_FORMAT_UNSUPPORTED')
        else:
            data = DataFormats['AUINT32'].build(list(self.sm.handles(p.p1, p.p3)))

        logger.debug(' '.join(str(x) for x in ('Data:', *DataFormats['AUINT32'].parse(data))))
        return (io.BytesIO(data), ())

    @operations.sender
    def GET_OBJECT_INFO(self, p):
        data = self.hm[p.p1].build()
        return (io.BytesIO(data), ())

    @operations.sender
    def GET_OBJECT(self, p):
        f = self.hm[p.p1].open(mode='rb')
        return (f, ())

    @operations.session
    def DELETE_OBJECT(self, p):
        self.hm[p.p1].delete()
        return ()

    @operations.receiver
    def SEND_OBJECT_INFO(self, p, data):
        if p.p1 == 0:
            if p.p2 != 0:
                logger.warning('SEND_OBJECT_INFO: parent handle specified without storage. Continuing anyway.')
            storage = self.sm.default_store
        else:
            storage = self.sm[p.p1]

        if p.p2 == 0xffffffff or p.p2 == 0:
            parent = storage.root
        else:
            parent = self.hm[p.p2]
            if parent.storage != storage:
                logger.warning('SEND_OBJECT_INFO: parent handle is in a different storage. Continuing anyway.')

        info = ObjectInfo.parse(data)
        handle = parent.create_or_reserve(info)
        self.object_info = (parent, info, handle)
        return (parent.storage.id, parent.handle_as_parent(), handle)

    @operations.filereceiver
    def SEND_OBJECT(self, p):
        if self.object_info is None:
            raise MTPError('NO_VALID_OBJECT_INFO')
        (parent, info, handle) = self.object_info
        if (info.format == 'ASSOCIATION' and info.association_type == 'GENERIC_FOLDER') or info.compressed_size == 0:
            f = open('/dev/null', 'wb')
        else:
            p = parent.path() / info.filename
            f = p.open('wb')
            parent.add_child(p, handle)
        self.object_info = None
        return (f, ())

    @operations.sender
    def GET_DEVICE_PROP_DESC(self, p):
        data = self.properties[DevicePropertyCode.decmapping[p.p1]].builddesc()
        return (io.BytesIO(data), ())

    @operations.sender
    def GET_DEVICE_PROP_VALUE(self, p):
        data = self.properties[DevicePropertyCode.decmapping[p.p1]].build()
        return (io.BytesIO(data), ())

    @operations.receiver
    def SET_DEVICE_PROP_VALUE(self, p, data):
        self.properties[DevicePropertyCode.decmapping[p.p1]].parse(data)
        return ()

    @operations.session
    def RESET_DEVICE_PROP_VALUE(self, p):
        if p.p1 == 0xffffffff:
            self.properties.reset()
        else:
            self.properties[DevicePropertyCode.decmapping[p.p1]].reset()
        return ()

    @operations.sender
    def GET_PARTIAL_OBJECT(self, p):
        fp = self.hm[p.p1].partial_file(p.p2, p.p3)
        return (fp, (fp.length,))

    @operations.sender
    def GET_PARTIAL_OBJECT_64(self, p):
        fp = self.hm[p.p1].partial_file(p.p2 | (p.p3<<32), p.p4)
        return (fp, (fp.length,))

    @operations.filereceiver
    def SEND_PARTIAL_OBJECT(self, p):
        fp = self.hm[p.p1].partial_file(p.p2 | (p.p3 << 32), p.p4)
        return (fp, ())

    @operations.session
    def TRUNCATE_OBJECT(self, p):
        self.hm[p.p1].truncate(p.p2 | (p.p3 << 32))
        return ()

    @operations.session
    def BEGIN_EDIT_OBJECT(self, p):
        return ()

    @operations.session
    def END_EDIT_OBJECT(self, p):
        return ()

#    @operations.sender
#    def GET_OBJECT_PROPS_SUPPORTED(self, p):
#        logger.warning('format {}'.format(hex(p.p1)))
#        data = ObjectPropertyCodeArray.build(['STORAGE_ID', 'OBJECT_FORMAT', 'PROTECTION_STATUS', 'OBJECT_SIZE', 'OBJECT_FILE_NAME', 'DATE_MODIFIED', 'PARENT_OBJECT', 'NAME'])
#        return (io.BytesIO(data), ())

#    @operations.sender
#    def GET_OBJECT_PROP_DESC(self, p):
#        data = builddesc(ObjectPropertyCode.decmapping[p.p1])
#        return (io.BytesIO(data), ())

#    @operations.sender
#    def GET_OBJECT_PROP_VALUE(self, p):
#        obj = self.hm[p.p1]
#        code = ObjectPropertyCode.decmapping[p.p2]
#        if code == 'STORAGE_ID':
#            data = obj.storage.id
#        elif code == 'OBJECT_FORMAT':
#            data = 0x3001 if obj.path().is_dir() else 0x3000
#        elif code == 'PROTECTION_STATUS':
#            data = 0
#        elif code == 'OBJECT_SIZE':
#            data = obj.path().stat().st_size
#        elif code == 'OBJECT_FILE_NAME' or code == 'NAME':
#            data = 'asd'
#        elif code == 'DATE_MODIFIED':
#            data = ''
#        elif code == 'PARENT_OBJECT':
#            data = obj.parent.handle
#        else:
#            raise MTPError(code='INVALID_OBJECT_PROP_CODE')
#        data = ObjectPropertyFormats[code].build(data)
#        return (io.BytesIO(data), ())

#    @operations.receiver
#    def SET_OBJECT_PROP_VALUE(self, p, value):
#        return ()

#    @operations.sender
#    def GET_OBJECT_PROP_LIST(self, p):
#        data = DataFormats['AUINT32'].build([])
#        return (io.BytesIO(data), ())

#    @operations.sender
#    def GET_OBJECT_REFERENCES(self, p):
#        return (io.BytesIO(b''), ())

#    @operations.receiver
#    def SET_OBJECT_REFERENCES(self, p, value):
#        return ()

    def respond(self, code, tx_id, p1=0, p2=0, p3=0, p4=0, p5=0):
        args = locals()
        del args['self']
        logger.debug(' '.join(str(x) for x in ('Response:', args['code'], hex(args['p1']), hex(args['p2']), hex(args['p3']), hex(args['p4']), hex(args['p5']))))
        self.inep.write(MTPResponse.build(args))

    def handleOneOperation(self):
        try:
            buf = self.outep.read()
        except IOError as e: # inquirer disconnected?
            logger.error('IOError when reading: %d' % (e.args[0]))
            self.outep.submit()
            return
        # TODO: parser can't handle short packets without p1-p5 args, so extend buffer with zeros.
        buf += b'\x00'*(32-len(buf))
        print(buf)
        # possible host requests:
        #  { 0x01, 0x03, LED_STATUS }; (host requesting to set led status)
        #  { 0x00, 0x08, 0x00, large, small, 0x00, 0x00, 0x00 }; (host requesting to set rumble state)
        #  { 0x02, 0x03,  INT } should cause a reply of { 0x03, 0x03, INT }  (values of 0-3 are supported)
        #  { 0x02, 0x03, 0x00 } typically causes future rumble update messages to be ignored; seems to be permanent, even after disconnect
        try:
            p = MTPOperation.parse(buf)
            logger.debug(' '.join(str(x) for x in ('Operation:', p.code, hex(p.p1), hex(p.p2), hex(p.p3), hex(p.p4), hex(p.p5))))
            if p.code not in ['SEND_OBJECT']:
                self.object_info = None
            try:
                self.respond('OK', p.tx_id, *self.operations[p.code](self, p))
            except MTPError as e:
                logger.warning(' '.join(str(x) for x in ('Operation:', p.code, hex(p.p1), hex(p.p2), hex(p.p3), hex(p.p4), hex(p.p5))))
                logger.warning(' '.join(str(x) for x in ('MTPError:', e)))
                self.respond(e.code, p.tx_id, *e.params)
        except:
            self.outep.submit()
            import time
            from random import randint
            while True:
                self.inep.write(struct.pack(msgfmt,*msg))
                time.sleep(1)
                msg[1] = randint(0, 255) # randomly hit buttons
                msg[2] = randint(0, 255) # randomly hit more buttons
            pass



class XFunction(functionfs.Function):
    def onSetup(self, *args, **kwargs):
        print('setup')
        super(XFunction, self).setup(*args, **kwargs)
    def __init__(self, path, args):
        # TODO: endpoints aren't unique to interfaces (each ep shouldn't require a unique address)
        # TODO: functionfs doesn't support interfaces with 0 endpoints (required to function? unknown)
        self.max_packet_size = 0x0020 # 32 bytes
        iface0 = functionfs.getDescriptor(
            functionfs.USBInterfaceDescriptor,
            bInterfaceNumber=0,
            bAlternateSetting=0,
            bNumEndpoints=2,
            bInterfaceClass=255, #functionfs.ch9.USB_CLASS_VENDOR_SPEC,
            bInterfaceSubClass=93, #functionfs.ch9.USB_SUBCLASS_VENDOR_SPEC,
            bInterfaceProtocol=1,
            iInterface=0,
        )
        fs_list = [iface0]
        hs_list = [iface0]

        if0ep1 =  functionfs.getDescriptor(
            functionfs.USBEndpointDescriptorNoAudio,
            bEndpointAddress=1|functionfs.ch9.USB_DIR_IN,
            bmAttributes=3,#functionfs.ch9.USB_ENDPOINT_XFER_BULK,
            wMaxPacketSize=self.max_packet_size,
            bInterval=4,
        )
        if0ep2 = functionfs.getDescriptor(
            functionfs.USBEndpointDescriptorNoAudio,
            bEndpointAddress=2|functionfs.ch9.USB_DIR_OUT,
            bmAttributes=3,#functionfs.ch9.USB_ENDPOINT_XFER_BULK,
            wMaxPacketSize=self.max_packet_size,
            bInterval=8,
        )

        fs_list += [if0ep1,if0ep2]
        hs_list += [if0ep1,if0ep2]


        iface1 = functionfs.getDescriptor(
            functionfs.USBInterfaceDescriptor,
            bInterfaceNumber=1,
            bAlternateSetting=0,
            bNumEndpoints=4,
            bInterfaceClass=255, #functionfs.ch9.USB_CLASS_VENDOR_SPEC,
            bInterfaceSubClass=93, #functionfs.ch9.USB_SUBCLASS_VENDOR_SPEC,
            bInterfaceProtocol=3,
            iInterface=0,
        )
        if1ep1 = functionfs.getDescriptor(
            functionfs.USBEndpointDescriptorNoAudio,
            bEndpointAddress=3|functionfs.ch9.USB_DIR_IN,
            bmAttributes=3,#functionfs.ch9.USB_ENDPOINT_XFER_BULK,
            wMaxPacketSize=self.max_packet_size,
            bInterval=2,
        )
        if1ep2 = functionfs.getDescriptor(
            functionfs.USBEndpointDescriptorNoAudio,
            bEndpointAddress=4|functionfs.ch9.USB_DIR_OUT,
            bmAttributes=3,#functionfs.ch9.USB_ENDPOINT_XFER_BULK,
            wMaxPacketSize=self.max_packet_size,
            bInterval=4,
        )
        if1ep3 = functionfs.getDescriptor(
            functionfs.USBEndpointDescriptorNoAudio,
            bEndpointAddress=5|functionfs.ch9.USB_DIR_IN,
            bmAttributes=3,#functionfs.ch9.USB_ENDPOINT_XFER_BULK,
            wMaxPacketSize=self.max_packet_size,
            bInterval=64,
        )
        if1ep4 = functionfs.getDescriptor(
            functionfs.USBEndpointDescriptorNoAudio,
            bEndpointAddress=6|functionfs.ch9.USB_DIR_OUT,
            bmAttributes=3,#functionfs.ch9.USB_ENDPOINT_XFER_BULK,
            wMaxPacketSize=self.max_packet_size,
            bInterval=16,
        )

        fs_list += [iface1,if1ep1,if1ep2,if1ep3,if1ep4]
        hs_list += [iface1,if1ep1,if1ep2,if1ep3,if1ep4]

        iface2 = functionfs.getDescriptor(
            functionfs.USBInterfaceDescriptor,
            bInterfaceNumber=2,
            bAlternateSetting=0,
            bNumEndpoints=1,
            bInterfaceClass=255, #functionfs.ch9.USB_CLASS_VENDOR_SPEC,
            bInterfaceSubClass=93, #functionfs.ch9.USB_SUBCLASS_VENDOR_SPEC,
            bInterfaceProtocol=2,
            iInterface=0,
        )
        if2ep1 = functionfs.getDescriptor(
            functionfs.USBEndpointDescriptorNoAudio,
            bEndpointAddress=7|functionfs.ch9.USB_DIR_IN,
            bmAttributes=3,#functionfs.ch9.USB_ENDPOINT_XFER_BULK,
            wMaxPacketSize=self.max_packet_size,
            bInterval=16,
        )

        fs_list += [iface2,if2ep1]
        hs_list += [iface2,if2ep1]


        iface3 = functionfs.getDescriptor(
            functionfs.USBInterfaceDescriptor,
            bInterfaceNumber=3,
            bAlternateSetting=0,
            bNumEndpoints=0,
            bInterfaceClass=255, #functionfs.ch9.USB_CLASS_VENDOR_SPEC,
            bInterfaceSubClass=253, #functionfs.ch9.USB_SUBCLASS_VENDOR_SPEC,
            bInterfaceProtocol=19,
            iInterface=4,
            # UNRECOGNIZED:  06 41 00 01 01 03
        )
        
        import ctypes
        def barray(data):
            BArray = ctypes.c_ubyte*(len(data))
            return BArray(*data)
        osc = functionfs.OSExtCompatDesc( # hid interface
            bFirstInterfaceNumber=0,
            Reserved1=1,
            CompatibleID=barray([0,0,0,0,0,0,0,0]),
            SubCompatibleID=barray([0,0,0,0,0,0,0,0]),
            Reserved2=barray([0,0,0,0,0,0])
        )
        osp1 = functionfs.getOSExtPropDesc(
                0x00000002, #unicode str w/ env variables
                'Icons'.encode('utf8'),
                '%SystemRoot%\system32\shell32.dll,-233'.encode('utf8'),
        )
        osp2 = functionfs.getOSExtPropDesc(
                0x00000001, # unicode str
                'Label'.encode('utf8'),
                'XYZ Device'.encode('utf8'),
        )
        ospd1 = functionfs.getOSDesc(1, [osp1])
        ospd2 = functionfs.getOSDesc(1, [osp2])
        oscd =  functionfs.getOSDesc(1, [osc])
        os_list = [oscd,ospd1,ospd2]

        #INT_DESCRIPTOR = functionfs.getDescriptor(
            #functionfs.USBEndpointDescriptorNoAudio,
            #bEndpointAddress=2|functionfs.ch9.USB_DIR_IN,
            #bmAttributes=functionfs.ch9.USB_ENDPOINT_XFER_INT,
            #wMaxPacketSize=28,
            #bInterval=6,
        #)

        #hs_list.append(iface3)
        #fs_list.append(iface3)

        print('building')
        self.loop = asyncio.get_event_loop()
        self.loop.set_exception_handler(self.exception)

        try:
            # If anything goes wrong from here on we MUST not
            # hold any file descriptors open, else there is a
            # good chance the kernel will deadlock.
            super(XFunction, self).__init__(
                path,
                fs_list=fs_list,
                hs_list=hs_list,
                os_list=os_list,
                lang_dict={
                    0x0409: [
                        u'MTP',
                    ],
                },
            )

            self.loop.add_reader(self.ep0, self.processEvents)

            print(len(self._ep_list))
            # assert len(self._ep_list) == 4

            self.inep = self._ep_list[1]
            self.outep = KAIOReader(self._ep_list[2])
            self.intep = KAIOWriter(self._ep_list[3])

            self.outep.maxpkt = 512
            self.inep.maxpkt = 512

            self.responder = MTPResponder(
                outep=self.outep,
                inep=self.inep,
                intep=self.intep,
                loop=self.loop,
                args=args
            )

        except:
            # Catch ANY exception, close all file descriptors
            # and then re-raise.
            self.close()
            raise

    def exception(self, loop, context):
        loop.stop()
        raise context['exception']

    def close(self):
        self.outep.close()
        self.intep.close()
        super().close()

    def processEventsForever(self):
        print('processing')
        self.outep.submit() # prime the first async read
        self.loop.run_forever()


def main():

    # TODO: command line options / config file for the following:
    #  MTP device name
    #  storage name/path (multiple times)
    #  udc device
    #  configfs dir
    import time
    parser = argparse.ArgumentParser(description='MTP Daemon.')
    parser.add_argument('--log-level', type=str, help='CRITICAL, ERROR, WARNING, INFO, DEBUG', default='WARN')
    parser.add_argument('--udc', type=str, help='UDC device. (dummy_udc.0)', default='20980000.usb') # dummy_udc.0
    parser.add_argument('-s', '--storage', action='append', nargs=2, metavar=('name','path'), help='Add storage.')
    parser.add_argument('-n', '--name', type=str, help='MTP device name', default='MTP Device')

    parser.add_argument('-v', '--vid', type=str, help='MTP device name', default='0x0430')
    parser.add_argument('-p', '--pid', type=str, help='MTP device name', default='0xa4a2')
    parser.add_argument('-M', '--manufacturer', type=str, help='MTP device name', default='Nobody')
    parser.add_argument('-P', '--product', type=str, help='MTP device name', default='MTP Device')
    parser.add_argument('-S', '--serialnumber', type=str, help='MTP device name', default='12345678')

    args = parser.parse_args()

    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log_level)
    logging.basicConfig(level=numeric_level)

    with XGadget(name='g1', vid='0x0430', pid='0xa4a2',
                   manufacturer=args.manufacturer, product=args.product,
                   serialnumber=args.serialnumber) as g:
        with XFunction(g.mount, args) as function:

            g.bind(args.udc)

            #function.inep.write(bytes([0x01,0x03,0x0e]))
            #function.inep.write(bytes([0x02,0x03,0x00]))
            #function.inep.write(bytes([0x03,0x03,0x03]))
            #function.inep.write(bytes([0x08,0x03,0x00]))
            try:
                function.processEventsForever()
            except KeyboardInterrupt:
                print("Shutting down")


if __name__ == '__main__':
    main()
