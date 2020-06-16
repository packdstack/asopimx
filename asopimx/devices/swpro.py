#!/usr/bin/python3

# NOTE: hiddr-convert failed to parse this descriptor
# (parsable @ http://eleccelerator.com/usbdescreqparser/)

from traceback import format_exc
from struct import *
from collections import namedtuple
import base64
import struct
import logging

from asopimx.profiles import Profile
from asopimx.devices import Gamepad
from asopimx.tools import phexlify, decode_bools, encode_bools
from asopimx.devices import Device

_logger = logging.getLogger(__name__ if __name__ != '__main__' else __file__)
logging.basicConfig()
_logger.setLevel(logging.INFO) # logging.getLevelName('INFO')

class SWPRO():
    # TODO: work out state management
    
    name = 'Switch Pro'
    code = 'swpro'
    products = {
        (0x057e,0x2009),
    }

    # transforms
    bmap = {0:1,1:2, 2:0,3:3,}
    hmap = {
        8:2, 4:6,2:0,1:4,
        10:1,6:7,9:3,5:5,
    }


    usb_bcd = '0x020' # 02.00 # (USB2)
    vendor_id = '0x057e' # 1406  # idVendor
    product_id = '0x2009' # 8201 Batoh Device / PlayStation 3 Controller # idProduct
    device_bcd = '0x0113' # 1.19 # bcdDevice
    manufacturer = '0' # 1 # iManufacturer
    product = 'Pro Controller' # 2 iProduct
    serial = '0' # iSerial
    configuration = 'Human Interface Device' # TODO: find out if there's anything relevant to put here
    max_power = '500' # 500mA # MaxPower
    
    # hid data
    protocol = '0' # bInterfaceProtocol
    subclass = '0' # bInterfaceSubClass

    report_desc = [
        0x05, 0x01,        #  Usage Page (Generic Desktop Ctrls)
        0x09, 0x05,        #  Usage (Game Pad)
        0xA1, 0x01,        #  Collection (Application)
        0x06, 0x01, 0xFF,  #    Usage Page (Vendor Defined 0xFF01)
        0x85, 0x21,        #    Report ID (33)
        0x09, 0x21,        #    Usage (0x21)
        0x75, 0x08,        #    Report Size (8)
        0x95, 0x30,        #    Report Count (48)
        0x81, 0x02,        #    Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x85, 0x30,        #    Report ID (48)
        0x09, 0x30,        #    Usage (0x30)
        0x75, 0x08,        #    Report Size (8)
        0x95, 0x30,        #    Report Count (48)
        0x81, 0x02,        #    Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x85, 0x31,        #    Report ID (49)
        0x09, 0x31,        #    Usage (0x31)
        0x75, 0x08,        #    Report Size (8)
        0x96, 0x69, 0x01,  #    Report Count (361)
        0x81, 0x02,        #    Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x85, 0x32,        #    Report ID (50)
        0x09, 0x32,        #    Usage (0x32)
        0x75, 0x08,        #    Report Size (8)
        0x96, 0x69, 0x01,  #    Report Count (361)
        0x81, 0x02,        #    Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x85, 0x33,        #    Report ID (51)
        0x09, 0x33,        #    Usage (0x33)
        0x75, 0x08,        #    Report Size (8)
        0x96, 0x69, 0x01,  #    Report Count (361)
        0x81, 0x02,        #    Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x85, 0x3F,        #    Report ID (63)
        0x05, 0x09,        #    Usage Page (Button)
        0x19, 0x01,        #    Usage Minimum (0x01)
        0x29, 0x10,        #    Usage Maximum (0x10)
        0x15, 0x00,        #    Logical Minimum (0)
        0x25, 0x01,        #    Logical Maximum (1)
        0x75, 0x01,        #    Report Size (1)
        0x95, 0x10,        #    Report Count (16)
        0x81, 0x02,        #    Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x05, 0x01,        #    Usage Page (Generic Desktop Ctrls)
        0x09, 0x39,        #    Usage (Hat switch)
        0x15, 0x00,        #    Logical Minimum (0)
        0x25, 0x07,        #    Logical Maximum (7)
        0x75, 0x04,        #    Report Size (4)
        0x95, 0x01,        #    Report Count (1)
        0x81, 0x42,        #    Input (Data,Var,Abs,No Wrap,Linear,Preferred State,Null State)
        0x05, 0x09,        #    Usage Page (Button)
        0x75, 0x04,        #    Report Size (4)
        0x95, 0x01,        #    Report Count (1)
        0x81, 0x01,        #    Input (Const,Array,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x05, 0x01,        #    Usage Page (Generic Desktop Ctrls)
        0x09, 0x30,        #    Usage (X)
        0x09, 0x31,        #    Usage (Y)
        0x09, 0x33,        #    Usage (Rx)
        0x09, 0x34,        #    Usage (Ry)
        0x16, 0x00, 0x00,  #    Logical Minimum (0)
        0x27, 0xFF, 0xFF, 0x00, 0x00,  #    Logical Maximum (65534)
        0x75, 0x10,        #    Report Size (16)
        0x95, 0x04,        #    Report Count (4)
        0x81, 0x02,        #    Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x06, 0x01, 0xFF,  #    Usage Page (Vendor Defined 0xFF01)
        0x85, 0x01,        #    Report ID (1)
        0x09, 0x01,        #    Usage (0x01)
        0x75, 0x08,        #    Report Size (8)
        0x95, 0x30,        #    Report Count (48)
        0x91, 0x02,        #    Output (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position,Non-volatile)
        0x85, 0x10,        #    Report ID (16)
        0x09, 0x10,        #    Usage (0x10)
        0x75, 0x08,        #    Report Size (8)
        0x95, 0x30,        #    Report Count (48)
        0x91, 0x02,        #    Output (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position,Non-volatile)
        0x85, 0x11,        #    Report ID (17)
        0x09, 0x11,        #    Usage (0x11)
        0x75, 0x08,        #    Report Size (8)
        0x95, 0x30,        #    Report Count (48)
        0x91, 0x02,        #    Output (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position,Non-volatile)
        0x85, 0x12,        #    Report ID (18)
        0x09, 0x12,        #    Usage (0x12)
        0x75, 0x08,        #    Report Size (8)
        0x95, 0x30,        #    Report Count (48)
        0x91, 0x02,        #    Output (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position,Non-volatile)
        0xC0,              #  End Collection
        # 0x00,            #  Unknown (bTag: 0x00, bType: 0x00)
    ] # 171 bytes (-1 (trailing unknown))

    report_length = str(len(report_desc)) # wDescriptorLength (NOTE: this should mach lenth of resport_desc below)
    # example:
    #   LB1A1    L34
    #   RB2B2    R38
    #   LT4X4    SL1
    #   RT8Y8    ST2
    # 3F 10     00   08 A0 80 0F 80 50 80 4F 80
    #    Dig Bttns   HT    LS    LS    RS    RS   

    def __init__(self, *args, **kwargs):
        self.State = namedtuple('State', 'u1 bset1 bset2 h u2 x u3 y u4 z u5 r')
        self.format = struct.Struct('B' * 12)
        self.neutral = self.State(
            0x3F,
            0x00, 0x00, # buttons
            0x08, # hat
            0xA0, 0x80, 0x0F, 0x80, # u,x,u,y
            0x50, 0x80, 0x4F, 0x80, # u,z,u,r
        ) 
        self.state = self.neutral

        # 0-15
        self.sdbuttons = dict((i, i) for i in range(0,16))
        # 0-5; x, y, z(rx), r(ry), hatrlud
        self.saxi = dict((i, i) for i in range(0,4))
        super(SWPRO,self).__init__(*args, **kwargs)

    def repack(self):
        ''' repack state for transfer (to host)
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
        # TODO: simplify this
        s = self.state
        package = self.format.pack(
            s.u1, s.bset1,
            s.bset2, s.h,
            s.u2, s.x, s.u3, s.y, s.u4, s.z, s.u5, s.r
        )
        #print(phexlify(package), end='\r')
        return package

    def transform_cc(self, lstate):
        ''' build capabilities class state from local state '''
        #self.cstate = self.cstate._replace(**{'bset1':lstate.bset1,'bset2':lstate.bset2})

        bstates = decode_bools(lstate.bset1, 16)
        btransform = decode_bools(lstate.bset1, 16)
        # remap buttons 1-4
        for k, v in self.bmap.items():
            btransform[v] = bstates[k]
        bset1 = encode_bools(btransform)
        # adjust axi sensitivity
        axi = {'x': lstate.x, 'y':lstate.y, 'z':lstate.z,'r':lstate.r}
        for k, v in axi.items():
            if v <= 120:
               axi[k] = max(int(((v - 120) * 1.5) + 120), 0) 
            elif v >= 134:
               axi[k] = min(int(((v - 134) * 1.5) + 134), 255)
        hmap = dict([(v,k) for k,v in self.hmap.items()])
        h = hmap.get(lstate.h, 0)
        hs = decode_bools(h, 4)
        self.cstate = self.CState(
            bset1, lstate.bset2,
            axi['x'], axi['y'],
            axi['z'], axi['r'],
            hs[3], hs[2], hs[1], hs[0], # TODO: hat
            0, 0, 0, 0, 0, 0, 0, 0, # TODO: analog buttons
        )
        return self.cstate

    def transform_local(self, cstate):
        ''' build local state from capabilities class state '''

        bstates = decode_bools(cstate.bset1, 16)
        btransform = decode_bools(cstate.bset1, 16)
        # remap buttons 1-4
        for k, v in self.bmap.items():
            btransform[k] = bstates[v]
        bset1=encode_bools(btransform)

        # hat
        # TODO: figure out a better way to do this
        hvals = [self.cstate.hr, self.cstate.hl, self.cstate.hu, self.cstate.hd]
        hvals.reverse()
        hv = encode_bools(hvals)
        h = self.hmap.get(hv, 8)
 
        self.state = self.State(
            self.state.u1,
            bset1, cstate.bset2,
            h, # 0x08, hat
            self.state.u2,
            cstate.x,
            self.state.u3,
            cstate.y,
            self.state.u4,
            cstate.z,
            self.state.u5,
            cstate.r,
        )
        return self.state

    def update_axis(self, id, value):
        aid = self.saxi.get(id, None)
        amap = {0:'x', 1:'y', 2:'z', 3:'r'}
        if aid is None or id not in amap:
            print('not mapped')
            return

        print(value)
        avalue = int((value / 32767.0) * 128) + 128
        print(avalue)
        if avalue > 255:
            avalue = 255
        print(amap[id])
        self.state.__dict__[amap[id]] = avalue
        self.state = self.state._replace(**{amap[id]: avalue})
        print(self.state)

    def update_button(self, id, value):
        bid = self.sbuttons.get(id, None)
        if bid is None:
            print('not mapped')
            return
        # TODO: pick button block depending on bid
        bstates = self.state.bset1
        bbstates = self.decode_bools(bstates, 16)
        bbstates[bid] = True if value else False
        print(bbstates)
        self.state = self.state._replace(bset1=self.encode_bools(bbstates))
        print(self.state.bset1)
        return


class SWPROProfile(SWPRO,Profile):
    pass

class SWPROPC(SWPRO,Gamepad):
    def __init__(self, device=None):
        super(SWPROPC, self).__init__()
        if device:
            self.assign_device(device)
    def assign_device(self, device):
        self.dev = device # new-style device
        self.device = device.dev # phys device

    def assign_profile(self, profile):
        ''' assign a profile to push/pull states to/from '''
        self.profile = profile
    def unpack(self, data):
        ''' get data message, translate it to capability class state '''
        try:
            s = self.format.unpack(data)
        except Exception as e:
            _logger.warn(e)
            return self.state
        return self.State(*s)
        # TODO: translate state tp capability class state
    def read(self, data):
        ''' "Read" data from phys device (recorded data can be passed in for testing)'''
        if not data:
            return
        self.state = self.unpack(data)
        self.send_profile()
    def send_profile(self):
        ''' send current state to profile
        TODO: (in inherited device's state format (ie. Gamepad)
        '''
        # TODO: support raw send if device and profile match (no translation wanted/needed)
        self.cstate = self.transform_cc(self.state)
        self.profile.recv_dev(self.cstate)
    def listen(self):
        while True:
            # TODO: handle timeouts
            data = bytes(self.device.read(64))
            self.read(data)

if __name__ == '__main__':
    import argparse
    import sys
    from tools import phexlify
    parser = argparse.ArgumentParser(description='if no arguments specified, registers profile')
    parser.add_argument('-c', '--clean', default=False, action='store_true')
    parser.add_argument('-t', '--test', default=False, action='store_true')
    args = parser.parse_args()
    profile = SWPROProfile(path='/dev/hidg0')
    if args.clean:
        profile.clean()
        sys.exit()
    try:
        if args.test:
            import hid
            d = Device()
            d.dev = hid.device()
            d.dev.open_path(b'/dev/hidraw0')
            con = SWPROPC()
            con.assign_profile(profile)
            con.assign_device(d)
            con.listen()
            sys.exit()
        profile.register()
    except SystemExit as e:
        pass
    except:
        _logger.warn(format_exc())

