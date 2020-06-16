#!/usr/bin/python3

# make menuconfig -> Device Drivers -> USB support -> 
#   USB Gadget Support -> USB functions configurable through configfs / Function filesystem (FunctionFS)
# modprobe libcomposite usb_f_fs

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
            os.makedirs(os.path.join(path, key), exist_ok=True)

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
        self.gadget.idVendor = '0x045e' # self.vid
        self.gadget.idProduct = '0x028e' # self.pid

        # os desciptor (example)
        # self.gadget.os_desc.use = '1'
        # self.gadget.os_desc.b_vendor_code = '0xcd'
        # self.gadget.os_desc.qw_sign = 'MSFT100'

        self.gadget.strings['0x409'].serialnumber = '3' # self.serialnumber
        self.gadget.strings['0x409'].manufacturer = '1' # self.manufacturer
        self.gadget.strings['0x409'].product = 'Xbox 360 Controller for Windows' # self.product (this will be shown when using mtp)

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

PENDING_READ_COUNT = 2
MAX_PENDING_WRITE_COUNT = 10

class XFunction(functionfs.Function):
    def onEnable(self):
        print('functionfs: ENABLE')
        print('Real interface 0:', self.ep0.getRealInterfaceNumber(0))
        import time
        cmds = [
            [0x01,0x03,0x0e],
            [0x02,0x03,0x00],
            [0x03,0x03,0x03],
            [0x08,0x03,0x00],
            [0x00,0x14,0x00,0x00,0x00,0x00,0x69,0xed,0x23,0xff,0x6b,0x00,0x15,0x03,0x00,0x00,0x00,0x00,0x00,0x00],
            [0x00,0x14,0x00,0x00,0x00,0x00,0xfc,0xec,0x23,0xff,0x6b,0x00,0x15,0x03,0x00,0x00,0x00,0x00,0x00,0x00],
        ]
        neutral = [
            0x00,0x14,0x00,0x00,0x00,0x00,0xfc,0xec,0x23,0xff,0x6b,0x00,0x15,0x03,0x00,0x00,0x00,0x00,0x00,0x00
        ]
        press_a = [
            0x00,0x14,0x00,0x08,0x00,0x00,0xfc,0xec,0x23,0xff,0x6b,0x00,0x15,0x03,0x00,0x00,0x00,0x00,0x00,0x00
        ]

        print('processing...')
        self.outep.submit() # prime the first async read
        for c in cmds:
            print('cmd: %s' % c)
            self.write(c)

    def onSetup(self, request_type, request, value, index, length):
        print('setup %s' % request_type)
        request_type_type = request_type & functionfs.ch9.USB_TYPE_MASK
        if request_type_type == functionfs.ch9.USB_TYPE_VENDOR:
            if request == common.REQUEST_ECHO:
                if (request_type & functionfs.ch9.USB_DIR_IN) == functionfs.ch9.USB_DIR_IN:
                    self.ep0.write(self.__echo_payload[:length])
                elif length:
                    self.__echo_payload = self.ep0.read(length)
            else:
                print('functionfs: onSetup: halt')
                self.ep0.halt(request_type)
        else:
            super(XFunction, self).onSetup(
                request_type, request, value, index, length,
            )

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

        #INT_DESCRIPTOR = functionfs.getDescriptor(
            #functionfs.USBEndpointDescriptorNoAudio,
            #bEndpointAddress=2|functionfs.ch9.USB_DIR_IN,
            #bmAttributes=functionfs.ch9.USB_ENDPOINT_XFER_INT,
            #wMaxPacketSize=28,
            #bInterval=6,
        #)

        #hs_list.append(iface3)
        #fs_list.append(iface3)

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
                lang_dict={
                    0x0409: [
                        u'MTP',
                    ],
                },
            )

            self.loop.add_reader(self.ep0, self.processEvents)

            print(len(self._ep_list))
            # assert len(self._ep_list) == 4

            print(self._ep_list)
            self.cmdep = KAIOWriter(self._ep_list[1])
            #self.inep = self._ep_list[1]
            self.outep = KAIOReader(self._ep_list[2])
            #self.intep = KAIOWriter(self._ep_list[3])

            self.outep.maxpkt = 512
            #self.inep.maxpkt = 512

            #self.responder = MTPResponder(
                #outep=self.outep,
                #inep=self.inep,
                #intep=self.intep,
                #loop=self.loop,
                #args=args
            #)

        except:
            # Catch ANY exception, close all file descriptors
            # and then re-raise.
            self.close()
            raise

    def write(self, value):
        """
        Queue write in kernel.
        value (bytes)
            Value to send.
        """
        ep = self.getEndpoint(1)
        ep.write(bytes(value))
        #self.cmdep.write(bytes(value))
        return
        aio_block = libaio.AIOBlock(
            libaio.AIOBLOCK_MODE_WRITE,
            self.getEndpoint(1),
            [bytearray(value)],
            0,
            self.eventfd,
            self._onCanSend,
        )
        self._aio_send_block_list.append(aio_block)
        self._aio_context.submit([aio_block])
        if len(self._aio_send_block_list) == MAX_PENDING_WRITE_COUNT:
            self._onCannotSend()


    def exception(self, loop, context):
        loop.stop()
        raise context['exception']

    def close(self):
        self.outep.close()
        #self.intep.close()
        super().close()

    def processEventsForever(self):
        import time
        cmds = [
            [0x01,0x03,0x0e],
            [0x02,0x03,0x00],
            [0x03,0x03,0x03],
            [0x08,0x03,0x00],
            [0x00,0x14,0x00,0x00,0x00,0x00,0x69,0xed,0x23,0xff,0x6b,0x00,0x15,0x03,0x00,0x00,0x00,0x00,0x00,0x00],
            [0x00,0x14,0x00,0x00,0x00,0x00,0xfc,0xec,0x23,0xff,0x6b,0x00,0x15,0x03,0x00,0x00,0x00,0x00,0x00,0x00],
        ]
        neutral = [
            0x00,0x14,0x00,0x00,0x00,0x00,0xfc,0xec,0x23,0xff,0x6b,0x00,0x15,0x03,0x00,0x00,0x00,0x00,0x00,0x00
        ]
        press_a = [
            0x00,0x14,0x00,0x08,0x00,0x00,0xfc,0xec,0x23,0xff,0x6b,0x00,0x15,0x03,0x00,0x00,0x00,0x00,0x00,0x00
        ]

        print('processing...')
        self.outep.submit() # prime the first async read
        for c in cmds:
            print('cmd: %s' % c)
            self.write(c)
        self.loop.run_forever()


        print('press a')
        for x in range(0,60):
            time.sleep(0.01)
            self.write(neutral)
        for x in range(0,60):
            time.sleep(0.01)
            self.write(press_a)


def main():

    # TODO: command line options / config file for the following:
    #  MTP device name
    #  storage name/path (multiple times)
    #  udc device
    #  configfs dir
    import time
    parser = argparse.ArgumentParser(description='MTP Daemon.')
    parser.add_argument('--log-level', type=str, help='CRITICAL, ERROR, WARNING, INFO, DEBUG', default='WARN')
    parser.add_argument(
        '--udc', type=str, default='20980000.usb',
        help='UDC device. ex: dummy_udc.0 / 20980000.usb (Pi0)'
    )
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

            try:
                function.processEventsForever()
            except KeyboardInterrupt:
                print("Shutting down")


if __name__ == '__main__':
    main()

