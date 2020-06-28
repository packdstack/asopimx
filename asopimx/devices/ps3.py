#!/usr/bin/python3

from traceback import format_exc
from struct import *
from collections import namedtuple
import base64
import time
import logging

from asopimx.profiles import Profile
from asopimx.devices import Gamepad

_logger = logging.getLogger(__name__ if __name__ != '__main__' else __file__)
logging.basicConfig()
_logger.setLevel(logging.INFO) # logging.getLevelName('INFO')

class PS3():
    # TODO: work out state management
    name = 'PS3 Controller'
    code = 'ps3'
    products = {
        (0x054c,0x0268),
    }

    
    usb_bcd = '0x020' # 02.00 # (USB2)
    vendor_id = '0x054c' # Sony Corp. # idVendor
    product_id = '0x0268' # Batoh Device / PlayStation 3 Controller # idProduct
    device_bcd = '0x0100' # 1.00 # bcdDevice
    manufacturer = 'Sony' # 1 # iManufacturer
    product = 'PLAYSTATION(R)3 Controller' # 2 iProduct
    serial = '0' # iSerial
    configuration = 'Human Interface Device' # TODO: find out if there's anything relevant to put here
    max_power = '500' # 500mA # MaxPower
    
    # hid data
    protocol = '0' # bInterfaceProtocol
    subclass = '0' # bInterfaceSubClass
    report_length = '148' # wDescriptorLength (NOTE: this should mach lenth of resport_desc below)

    report_desc = [
        0x05, 0x01,         #   Usage Page (Desktop),
        0x09, 0x04,         #   Usage (Joystick),
        0xA1, 0x01,         #   Collection (Application),
        0xA1, 0x02,         #       Collection (Logical),
        0x85, 0x01,         #           Report ID (1),
        0x75, 0x08,         #           Report Size (8),
        0x95, 0x01,         #           Report Count (1),
        0x15, 0x00,         #           Logical Minimum (0),
        0x26, 0xFF, 0x00,   #           Logical Maximum (255),
        0x81, 0x03,         #           Input (Constant, Variable),
    
        0x75, 0x01,         #           Report Size (1),
        0x95, 0x13,         #           Report Count (19),
        0x15, 0x00,         #           Logical Minimum (0),
        0x25, 0x01,         #           Logical Maximum (1),
        0x35, 0x00,         #           Physical Minimum (0),
        0x45, 0x01,         #           Physical Maximum (1),
        0x05, 0x09,         #           Usage Page (Button),
        0x19, 0x01,         #           Usage Minimum (01h),
        0x29, 0x13,         #           Usage Maximum (13h),
        0x81, 0x02,         #           Input (Variable),
    
        0x75, 0x01,         #           Report Size (1),
        0x95, 0x0D,         #           Report Count (13),
        0x06, 0x00, 0xFF,   #           Usage Page (FF00h),
        0x81, 0x03,         #           Input (Constant, Variable),
        0x15, 0x00,         #           Logical Minimum (0),
        0x26, 0xFF, 0x00,   #           Logical Maximum (255),
        0x05, 0x01,         #           Usage Page (Desktop),
        0x09, 0x01,         #           Usage (Pointer),
        0xA1, 0x00,         #           Collection (Physical),
        0x75, 0x08,         #               Report Size (8),
        0x95, 0x04,         #               Report Count (4),
        0x35, 0x00,         #               Physical Minimum (0),
        0x46, 0xFF, 0x00,   #               Physical Maximum (255),
        0x09, 0x30,         #               Usage (X),
        0x09, 0x31,         #               Usage (Y),
        0x09, 0x32,         #               Usage (Z),
        0x09, 0x35,         #               Usage (Rz),
        0x81, 0x02,         #               Input (Variable),
        0xC0,               #           End Collection,
        0x05, 0x01,         #           Usage Page (Desktop),
        0x75, 0x08,         #           Report Size (8),
        0x95, 0x27,         #           Report Count (39),
        0x09, 0x01,         #           Usage (Pointer),
        0x81, 0x02,         #           Input (Variable),
        0x75, 0x08,         #           Report Size (8),
        0x95, 0x30,         #           Report Count (48),
        0x09, 0x01,         #           Usage (Pointer),
        0x91, 0x02,         #           Output (Variable),
        0x75, 0x08,         #           Report Size (8),
        0x95, 0x30,         #           Report Count (48),
        0x09, 0x01,         #           Usage (Pointer),
        0xB1, 0x02,         #           Feature (Variable),
        0xC0,               #       End Collection,
        0xA1, 0x02,         #       Collection (Logical),
        0x85, 0x02,         #           Report ID (2),
        0x75, 0x08,         #           Report Size (8),
        0x95, 0x30,         #           Report Count (48),
        0x09, 0x01,         #           Usage (Pointer),
        0xB1, 0x02,         #           Feature (Variable),
        0xC0,               #       End Collection,
        0xA1, 0x02,         #       Collection (Logical),
        0x85, 0xEE,         #           Report ID (238),
        0x75, 0x08,         #           Report Size (8),
        0x95, 0x30,         #           Report Count (48),
        0x09, 0x01,         #           Usage (Pointer),
        0xB1, 0x02,         #           Feature (Variable),
        0xC0,               #       End Collection,
        0xA1, 0x02,         #       Collection (Logical),
        0x85, 0xEF,         #           Report ID (239),
        0x75, 0x08,         #           Report Size (8),
        0x95, 0x30,         #           Report Count (48),
        0x09, 0x01,         #           Usage (Pointer),
        0xB1, 0x02,         #           Feature (Variable),
        0xC0,               #       End Collection,
        0xC0                #   End Collection
    ]
    
    # report example:
    #[ # each entry = 1 byte (ex: "\0\0" = 2 bytes (2B))
    #    "\x1\0", # record id, padding
    #    "\x1\0", # buttons 1-16, (2 bytes; 16 bits, each button represented by one bit (either on or off) ex: \0 = all off, \x1 = 1 on, \x2 = 1,2 on
    #    "\0\0", # next 3 buttons, 17-19, are the first 3 bits of this byte (rest is padding)
    #    "\x83", # X axis
    #    "\x7d", # Y axis
    #    "\x81", # Z axis
    #    "\x80", # R axis
    #    # TODO
    #    "\0\0\0\0"
    #    "\0\0\0\0" hatu, hatr, hatd, hatl (non-standard?) (we may need to translate this to work in windows)
    #    "\0\0\0\0\0\0\0\0\0\0\0\x2\xee\x12\0\0\0\0\x12\xf8\x77\0\0\x2"
    #    "\x7\x1\xee\x1\x94\x1\xd7"
    #]

    def __init__(self):
        self.State = namedtuple('State', 'u1 u2 bset1 bset2 u3 u4 x y z r u5 hu hr hd hl u6 u7 u8 u9 u10 u11')
        self.format = Struct('B' * 12) # TODO
        self.lstate = self.State(
            1, 0,
            0, 0,
            0, 0,
            0, 0, 0, 0,
            0,
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0,
        ) 

        # 0-15
        self.sbuttons = dict((i, i) for i in range(0,16))
        self.sbuttons.update({
            # NOTE: original mappings don't map right
            0 : 1, # 'a'
            1 : 2, # 'b',
            2 : 0, # 'c',
            3 : 3, # 'x',
        })
        # 0-5; x, y, z(rx), r(ry), hatx, haty
        self.saxi = dict((i, i) for i in range(0,6))


    def repack(self):
        '''
        package = struct.pack(
            self.dformat,
            state.u1, state.u2,
            state.bset1, state.bset2,
            state.u3, state.u4,
            state.x, state.y, state.z, state.r,
            state.u5, state.u6, state.u7,
            state.u8, state.u9, state.u10, #state.u11,
        )
        '''
        package = base64.b16decode('01 00'.replace(' ', ''))
        package += struct.pack('H', self.lstate.bset1)
        # 16-buttons (binary)
        package += base64.b16decode('00 00'.replace(' ', ''))
        # l&r sticks (0-255)
        package += struct.pack('B', self.lstate.x)
        package += struct.pack('B', self.lstate.y)
        package += struct.pack('B', self.lstate.z)
        package += struct.pack('B', self.lstate.r)
        package += base64.b16decode('00 00 00 00'.replace(' ', ''))
        #package += base64.b16decode('00 00 00 83 7D 81 80 00 00 00 00 00 00'.replace(' ', ''))
        # hat (0-255)
        package += struct.pack('B', self.lstate.hu)
        package += struct.pack('B', self.lstate.hr)
        package += struct.pack('B', self.lstate.hd)
        package += struct.pack('B', self.lstate.hl)
        # TODO
        package += base64.b16decode('00 00 00 00 00 00 00 00 00 00 00 00 02 EE 12'.replace(' ', ''))
        package += base64.b16decode('00 00 00 00 12 F8 77 00'.replace(' ', ''))
        # x, y, z; (+/-)  right/left, forward/back, up/down(right-hand rule)
        # 02 = sixaxis rotation around the x axis
        # 03,01 = sixaxis rotation around the y axis
        # 04 = sixaxis rotation around the z axis
        # (byte before each of them are acceleration? detection of motion? orientation?)
        # (juding by hid report data, motion detection seems most likely)
        package += base64.b16decode('00 02 05 03 EF 01 93 04'.replace(' ', ''))
        return package

    def update_axis(self, id, value):
        aid = self.saxi.get(id, None)
        amap = {0:'x', 1:'y', 2:'z', 3:'r', 4:'hu', 5:'hr', 6:'hd', 7:'hl'}
        if aid is None or id not in amap:
            _logger.warning('not mapped')
            return

        avalue = int((value / 32767.0) * 128) + 128
        if avalue > 255:
            avalue = 255
        self.lstate.__dict__[amap[id]] = avalue
        self.lstate = self.lstate._replace(**{amap[id]: avalue})

    def update_button(self, id, value):
        bid = self.sbuttons.get(id, None)
        if bid is None:
            _logger.warning('not mapped')
            return
        # TODO: pick button block depending on bid
        bstates = self.lstate.bset1
        bbstates = self.decode_bools(bstates, 16)
        bbstates[bid] = True if value else False
        self.lstate = self.lstate._replace(bset1=self.encode_bools(bbstates))
        return

class PS3Profile(PS3,Profile):
    pass

class PS3Pad(PS3,Gamepad): # TODO
    def __init__(self, device=None):
        super(PS3Pad, self).__init__()
        if device:
            self.assign_device(device)
    def assign_device(self, device):
        self.dev = device # new-style device
        self.device = device.dev # phys device
    def assign_profile(self, profile):
        ''' assign a profile to push/pull states to/from '''
        self.profile = profile
    def listen(self):
        while True:
            # TODO: handle timeouts
            data = bytes(self.device.read(64))
            self.read(data)
            time.sleep(.1) # let the system breath
    def read(self, data):
        ''' "Read" data from phys device (recorded data can be passed in for testing)'''
        if not data:
            return
        self.state = self.unpack(data)
        self.send_profile()
    def unpack(self, data):
        ''' get data message, translate it to capability class state '''
        try:
            s = self.format.unpack(data)
        except Exception as e:
            _logger.warn(e)
            return self.state
        return self.State(*s)
        # TODO: translate state tp capability class state
    def send_profile(self):
        ''' send current state to profile
        TODO: (in inherited device's state format (ie. Gamepad)
        '''
        # TODO: support raw send if device and profile match (no translation wanted/needed)
        self.cstate = self.transform_cc(self.state)
        self.profile.recv_dev(self.cstate)


if __name__ == '__main__':
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clean', default=False, action='store_true')
    args = parser.parse_args()
    dev = PS3Profile()
    if args.clean:
        dev.clean()
        sys.exit()
    try:
        dev.register()
    except:
        _logger.warn(format_exc())
