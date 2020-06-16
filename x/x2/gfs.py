#!/usr/bin/python3

import os, stat
import os, subprocess, logging, argparse

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
        self.gadget.strings['0x409'].product = '2'

        # rndis os desc strings example (if providing rndis functionality)
        #self.gadget.functions['rndis.usb0'].os_desc['interface.rndis'].compatible_id = 'RNDIS'
        #self.gadget.functions['rndis.usb0'].os_desc['interface.rndis'].sub_compatible_id = '5162001'

        self.gadget.configs['c.1'].strings['0x409'].configuration = 'X'

        # other function combinations:
        #   'rndis.usb0', 'acm.GS0', 'acm.GS1', etc.
        # TODO: for composite devices, save these in a list
        self.fn_name, self.inst_name = 'ffs', 'omaley' # function name, instance name
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

from mtp.kaio import KAIOReader, KAIOWriter

FS_BULK_MAX_PACKET_SIZE = 64
HS_BULK_MAX_PACKET_SIZE = 512

import io

import logging
logger = logging.getLogger(__name__)

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
class XResponder(object):

    def __init__(self, outep, inep, loop):
        self.outep = outep
        self.inep = inep
        self.loop = loop
        self.loop.add_reader(self.outep, self.handle_request)

    def handle_request(self):
        try:
            buf = self.outep.read()
        except IOError as e: # inquirer disconnected?
            logger.error('IOError when reading: %d' % (e.args[0]))
            self.outep.submit()
            return

        print(buf)
        # possible host requests:
        #  { 0x01, 0x03, LED_STATUS }; (host requesting to set led status)
        #  { 0x00, 0x08, 0x00, large, small, 0x00, 0x00, 0x00 }; (host requesting to set rumble state)
        #  { 0x02, 0x03,  INT } should cause a reply of { 0x03, 0x03, INT }  (values of 0-3 are supported)
        #  { 0x02, 0x03, 0x00 } typically causes future rumble update messages to be ignored; seems to be permanent, even after disconnect
        self.outep.submit()
        import time
        from random import randint
        while True:
            self.inep.write(struct.pack(msgfmt,*msg))
            time.sleep(1)
            msg[1] = randint(0, 255) # randomly hit buttons
            msg[2] = randint(0, 255) # randomly hit more buttons


import fnfs

class XFunction(fnfs.Function):
    def __init__(self, path, args):
        # TODO: endpoints aren't unique to interfaces (each ep shouldn't require a unique address)
        # TODO: functionfs doesn't support interfaces with 0 endpoints (required to function? unknown)
        self.max_packet_size = 0x0020 # 32 bytes
        iface0 = self.describe(
            fnfs.Descriptor.Interface,
            bInterfaceNumber=0,
            bAlternateSetting=0,
            bNumEndpoints=2,
            bInterfaceClass=fnfs.Descriptor.Class.vendor_spec,
            bInterfaceSubClass=93,
            bInterfaceProtocol=1,
            iInterface=0,
        )

        if0ep1 =  self.describe(
            fnfs.Descriptor.Endpoint,
            bEndpointAddress=1|fnfs.USB.Dir.IN,
            bmAttributes=fnfs.USB.Endpoint.Xfer.int,
            wMaxPacketSize=self.max_packet_size,
            bInterval=4,
        )
        if0ep2 = self.describe(
            fnfs.Descriptor.Endpoint,
            bEndpointAddress=2|fnfs.USB.Dir.OUT,
            bmAttributes=fnfs.USB.Endpoint.Xfer.int,
            wMaxPacketSize=self.max_packet_size,
            bInterval=8,
        )

        ifaces = [self.Interface(iface0, [if0ep1,if0ep2])]

        iface1 = self.describe(
            fnfs.Descriptor.Interface,
            bInterfaceNumber=1,
            bAlternateSetting=0,
            bNumEndpoints=4,
            bInterfaceClass=fnfs.Descriptor.Class.vendor_spec,
            bInterfaceSubClass=93,
            bInterfaceProtocol=3,
            iInterface=0,
        )
        if1ep1 = self.describe(
            fnfs.Descriptor.Endpoint,
            bEndpointAddress=3|fnfs.USB.Dir.IN,
            bmAttributes=fnfs.USB.Endpoint.Xfer.int,
            wMaxPacketSize=self.max_packet_size,
            bInterval=2,
        )
        if1ep2 = self.describe(
            fnfs.Descriptor.Endpoint,
            bEndpointAddress=4|fnfs.USB.Dir.OUT,
            bmAttributes=fnfs.USB.Endpoint.Xfer.int,
            wMaxPacketSize=self.max_packet_size,
            bInterval=4,
        )
        if1ep3 = self.describe(
            fnfs.Descriptor.Endpoint,
            bEndpointAddress=5|fnfs.USB.Dir.IN,
            bmAttributes=fnfs.USB.Endpoint.Xfer.int,
            wMaxPacketSize=self.max_packet_size,
            bInterval=64,
        )
        if1ep4 = self.describe(
            fnfs.Descriptor.Endpoint,
            bEndpointAddress=6|fnfs.USB.Dir.OUT,
            bmAttributes=fnfs.USB.Endpoint.Xfer.int,
            wMaxPacketSize=self.max_packet_size,
            bInterval=16,
        )

        ifaces.append(self.Interface(iface1, [if1ep1, if1ep2, if1ep3, if1ep4]))

        iface2 = self.describe(
            fnfs.Descriptor.Interface,
            bInterfaceNumber=2,
            bAlternateSetting=0,
            bNumEndpoints=1,
            bInterfaceClass=fnfs.Descriptor.Class.vendor_spec,
            bInterfaceSubClass=93,
            bInterfaceProtocol=2,
            iInterface=0,
        )
        if2ep1 = self.describe(
            fnfs.Descriptor.Endpoint,
            bEndpointAddress=7|fnfs.USB.Dir.IN,
            bmAttributes=fnfs.USB.Endpoint.Xfer.int,
            wMaxPacketSize=self.max_packet_size,
            bInterval=16,
        )

        ifaces.append(self.Interface(iface2, [if2ep1]))

        iface3 = self.describe(
            fnfs.Descriptor.Interface,
            bInterfaceNumber=3,
            bAlternateSetting=0,
            bNumEndpoints=0,
            bInterfaceClass=fnfs.Descriptor.Class.vendor_spec,
            bInterfaceSubClass=93,
            bInterfaceProtocol=19,
            iInterface=4,
            # UNRECOGNIZED:  06 41 00 01 01 03
        )

        # TODO: this fails
        #ifaces.append(self.Interface(iface3))

        self.loop = asyncio.get_event_loop()
        self.loop.set_exception_handler(self.exception)

        try:
            # If anything goes wrong from here on we MUST not
            # hold any file descriptors open, else there is a
            # good chance the kernel will deadlock.
            super(XFunction, self).__init__(
                path, ifaces,
                langs={
                    0x0409: [
                        u'X Input',
                    ],
                },
            )

            self.loop.add_reader(self.e0, self.process)

            # assert len(self._ep_list) == 4

            self.inep = self._eps[1]
            self.outep = KAIOReader(self._eps[2])

            self.outep.maxpkt = 512
            self.inep.maxpkt = 512

            self.responder = XResponder(
                outep=self.outep,
                inep=self.inep,
                loop=self.loop,
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
        super().close()

    def process(self):
        import time
        from random import randint
        while True:
            self.inep.write(struct.pack(msgfmt,*msg))
            time.sleep(1)
            msg[1] = randint(0, 255) # randomly hit buttons
            msg[2] = randint(0, 255) # randomly hit more buttons
        if limit is None:
            self.outep.submit() # prime the first async read
            self.loop.run_forever()

    def run(self):
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
    parser.add_argument('--udc', type=str, help='UDC device. (dummy_udc.0)', default='dummy_udc.0')
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
                function.run()
            except KeyboardInterrupt:
                print("Shutting down")


if __name__ == '__main__':
    main()
