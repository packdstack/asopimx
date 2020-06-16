#!/usr/bin/python3

''' pure-python IOCTL and HID helpers (to extract HID report descriptors, dev. info, etc.)
# TODO: make this requests-level awesome
because everything else is a PITA (painful, lacks features, license-incompatible, or has no python api)
# TODO: add our own descriptor parser
'''

import ctypes
from enum import IntEnum
import fcntl

# input.h
class BUS(IntEnum):
    USB = 0x03
    HIL = 0x04
    BLUETOOTH = 0x05
    VIRTUAL = 0x06

class NR:
    bits = 8
    mask = (1 << bits) - 1
    shift = 0

class Type:
    bits = 8
    mask = (1 << bits) - 1
    shift = NR.shift + NR.bits

class Size:
    bits = 14
    mask = (1 << bits) - 1
    shift = Type.shift + Type.bits
    shifted_mask = mask << shift

class Dir:
    bits = 2
    mask = (1 << bits) - 1
    shift = Size.shift + Size.bits
    class IO(IntEnum):
        NONE = 0
        WRITE = 1
        READ = 2

class IOCTL:
    ''' ioctl request builder '''

    class Request:
        def __init__(self, nr, dir=None, type=None, size=None):
            # TODO: if dir, type or size is NONE and one of the others isn't, raise
            if dir is None or type is None or size is None:
                self.dir = (nr >> Dir.shift) & Dir.mask
                self.type = (nr >> Type.shift) & Type.mask
                self.nr = (nr >> NR.shift) & NR.mask
                self.size = (nr >> Size.shift) & Size.mask
            else:
                self.nr = nr
                self.dir = dir
                self.type = type
                self.size = size

    def send(dir, type, nr, size):
        ''' send (build) an ioctl request '''
        # sanity-check
        assert dir <= Dir.mask, dir
        assert type <= Type.mask, type
        assert nr <= NR.mask, nr
        assert size <= Size.mask, size

        return (dir << Dir.shift) | (type << Type.shift) | (nr << NR.shift) | (size << Size.shift)

    def check_type(t):
        ''' check type size and ioctl nr compatibility '''
        try:
            r = ctypes.sizeof(t)
            assert r <= Size.mask, r
        except TypeError:
            # TODO: filter number types; raise otherwise
            return t
        return r

    # convenience functions

    def noop(type, nr):
        ''' ioctl cmd w/ no parameters '''
        return IOCTL.send(Dir.IO.NONE, type, nr, 0)

    def read(type, nr, size):
        ''' ioctl cmd w/ read parameters '''
        return IOCTL.send(Dir.IO.READ, type, nr, IOCTL.check_type(size))

    def write(type, nr, size):
        ''' ioctl cmd w/ write parameters '''
        return IOCTL.send(Dir.IO.WRITE, type, nr, IOCTL.check_type(size))

    def request(type, nr, size):
        ''' ioctl cmd w/ read & write parameters '''
        return IOCTL.send(Dir.IO.WRITE | Dir.IO.READ, type, nr, IOCTL.check_type(size))


class HIDCTL:
    ''' HID IOCTL request builder '''
    # hid.h
    max_descriptor_size = 4096
    # hidraw.h
    type = ord('H') # 0x48; 72

    buffer_size = 64

class HIDCTL(HIDCTL):
    # hidraw.h
    class ReportDescriptor(ctypes.Structure):
        _fields_ = [
            ('size', ctypes.c_uint),
            ('value', ctypes.c_ubyte * HIDCTL.max_descriptor_size),
        ]

    class DevInfo(ctypes.Structure):
        _fields_ = [
            ('bus_type', ctypes.c_uint),
            ('vendor_id', ctypes.c_ushort),
            ('product_id', ctypes.c_ushort),
        ]
        def __str__(self):
            return "<%s bus_type:%s, vendor_id:%s, product_id:%s>" % (type(self), self.bus_type, hex(self.vendor_id), hex(self.product_id))

    def get_report_desc_size():
        desc_size = IOCTL.read(HIDCTL.type, 0x01, ctypes.c_int)
        return desc_size

    def get_report_desc():
        desc = IOCTL.read(HIDCTL.type, 0x02, HIDCTL.ReportDescriptor)
        return desc

    def get_info():
        info = IOCTL.read(HIDCTL.type, 0x03, HIDCTL.DevInfo)
        return info

    def get_name(size=512):
        return IOCTL.read(HIDCTL.type, 0x04, size)

    def get_address(size=512):
        return IOCTL.read(HIDCTL.type, 0x05, size)

    def send_feature(size):
        return IOCTL.request(HIDCTL.type, 0x06, size)

    def get_feature(size):
        return IOCTL.request(HIDCTL.type, 0x07, size)

class HID:
    ''' HID IOCTL interface '''
    def __init__(self, device):
        ''' device = file obj / fileno) '''
        self.device = device

    def ioctl(self, f, args, mutate=False):
        r = fcntl.ioctl(self.device, f, args, mutate)
        if r < 0:
            raise IOError(r)

    def get_report_desc(self):
        desc = HIDCTL.ReportDescriptor()
        size = ctypes.c_uint()
        self.ioctl(HIDCTL.get_report_desc_size(), size, True)
        desc.size = size
        self.ioctl(HIDCTL.get_report_desc(), desc, True)
        return bytes(desc.value[:size.value])

    def get_info(self):
        info = HIDCTL.DevInfo()
        self.ioctl(HIDCTL.get_info(), info, True)
        return info

    def get_name(self, size=512):
        name = ctypes.create_string_buffer(size)
        self.ioctl(HIDCTL.get_name(size), name, True)
        return name.value.decode('utf8')

    def get_address(self, size=512):
        address = ctypes.create_string_buffer(size)
        self.ioctl(HIDCTL.get_address(size), address, True)
        return address.value.decode('utf8')

    def send_report(self, report, id=0):
        # TODO: test this
        size = len(report) + 1
        bf = bytearray(size)
        bf[0] = id
        bf[1:] = report
        return self.ioctl(HIDCTL.send_feature(size), (ctypes.c_char * size).from_buffer(bf), True)

    def get_report(self, id=0, size=HIDCTL.buffer_size - 1):
        # TODO: test this
        size += 1
        bf = bytearray(size)
        bf[0] = id
        self.ioctl(HIDCTL.get_feature(size), (ctypes.c_char * size).from_buffer(bf), True)
        return bf

if __name__ == '__main__':
    import os, sys
    from binascii import hexlify
    import argparse
    parser = argparse.ArgumentParser(description='Unless specified, prints HID info & descriptor')
    parser.add_argument('file', help='Device File (ex. /dev/hidraw0')
    parser.add_argument('-r', '--raw', help='Print raw descriptor (only)', action='store_true')
    parser.add_argument('-x', '--hex', help='Print hex descriptor (only)', action='store_true')
    args = parser.parse_args()

    dev = HID(open(args.file))
    desc = dev.get_report_desc()
    if args.raw:
        # write binary report desc to stdout
        fp = os.fdopen(sys.stdout.fileno(), 'wb')
        fp.write(desc)
        fp.flush()
    elif(args.hex): # print in hex format
        print(hexlify(desc).decode('utf8'))
    else:
        print(hexlify(desc).decode('utf8'))
        print(dev.get_info())
        print(dev.get_name())
        print(dev.get_address())
        # print(dev.get_report())

