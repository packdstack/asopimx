#!/usr/bin/python3

from traceback import format_exc
from struct import *
from collections import namedtuple
import base64
import struct
import logging

from asopimx.profiles import Profile
from asopimx.devices import Gamepad
from asopimx.tools import phexlify

_logger = logging.getLogger(__name__ if __name__ != '__main__' else __file__)
logging.basicConfig()
_logger.setLevel(logging.INFO) # logging.getLevelName('INFO')

class MNSD():
    # TODO: work out state management
    
    name = 'Magic NS (D-Input)'
    code = 'mnsd'
    products = {
        (0x0079,0x18d2),
    }
    raw = False

    usb_bcd = '0x020' # 02.00 # (USB2)
    vendor_id = '0x0079' # Sony Corp. # idVendor
    product_id = '0x18d2' # Batoh Device / PlayStation 3 Controller # idProduct
    device_bcd = '0x0113' # 1.19 # bcdDevice
    manufacturer = '0' # 1 # iManufacturer
    product = 'MAGIC-NS' # 2 iProduct
    serial = '0' # iSerial
    configuration = 'Human Interface Device' # TODO: find out if there's anything relevant to put here
    max_power = '500' # 500mA # MaxPower
    
    # hid data
    protocol = '0' # bInterfaceProtocol
    subclass = '0' # bInterfaceSubClass
    report_length = '137' # wDescriptorLength (NOTE: this should mach lenth of resport_desc below)

    report_desc = [
        0x05, 0x01,         #  Usage Page (Desktop),            
        0x09, 0x05,         #  Usage (Gamepad),                 
        0xA1, 0x01,         #  Collection (Application),        
        0x15, 0x00,         #      Logical Minimum (0),         
        0x25, 0x01,         #      Logical Maximum (1),         
        0x35, 0x00,         #      Physical Minimum (0),        
        0x45, 0x01,         #      Physical Maximum (1),        
        0x75, 0x01,         #      Report Size (1),             
        0x95, 0x0D,         #      Report Count (13),           
        0x05, 0x09,         #      Usage Page (Button),         
        0x19, 0x01,         #      Usage Minimum (01h),         
        0x29, 0x0D,         #      Usage Maximum (0Dh),         
        0x81, 0x02,         #      Input (Variable),            
        0x95, 0x03,         #      Report Count (3),            
        0x81, 0x01,         #      Input (Constant),            
        0x05, 0x01,         #      Usage Page (Desktop),        
        0x25, 0x07,         #      Logical Maximum (7),         
        0x46, 0x3B, 0x01,   #      Physical Maximum (315),      
        0x75, 0x04,         #      Report Size (4),             
        0x95, 0x01,         #      Report Count (1),            
        0x65, 0x14,         #      Unit (Degrees),              
        0x09, 0x39,         #      Usage (Hat Switch),          
        0x81, 0x42,         #      Input (Variable, Null State),
        0x65, 0x00,         #      Unit,                        
        0x95, 0x01,         #      Report Count (1),            
        0x81, 0x01,         #      Input (Constant),            
        0x26, 0xFF, 0x00,   #      Logical Maximum (255),       
        0x46, 0xFF, 0x00,   #      Physical Maximum (255),      
        0x09, 0x30,         #      Usage (X),                   
        0x09, 0x31,         #      Usage (Y),                   
        0x09, 0x32,         #      Usage (Z),                   
        0x09, 0x35,         #      Usage (Rz),                  
        0x75, 0x08,         #      Report Size (8),             
        0x95, 0x04,         #      Report Count (4),            
        0x81, 0x02,         #      Input (Variable),            
        0x06, 0x00, 0xFF,   #      Usage Page (FF00h),          
        0x09, 0x20,         #      Usage (20h),                 
        0x09, 0x21,         #      Usage (21h),                 
        0x09, 0x22,         #      Usage (22h),                 
        0x09, 0x23,         #      Usage (23h),                 
        0x09, 0x24,         #      Usage (24h),                 
        0x09, 0x25,         #      Usage (25h),                 
        0x09, 0x26,         #      Usage (26h),                 
        0x09, 0x27,         #      Usage (27h),                 
        0x09, 0x28,         #      Usage (28h),                 
        0x09, 0x29,         #      Usage (29h),                 
        0x09, 0x2A,         #      Usage (2Ah),                 
        0x09, 0x2B,         #      Usage (2Bh),                 
        0x95, 0x0C,         #      Report Count (12),           
        0x81, 0x02,         #      Input (Variable),            
        0x0A, 0x21, 0x26,   #      Usage (2621h),               
        0x95, 0x08,         #      Report Count (8),            
        0xB1, 0x02,         #      Feature (Variable),          
        0x0A, 0x21, 0x26,   #      Usage (2621h),               
        0x91, 0x02,         #      Output (Variable),           
        0x26, 0xFF, 0x03,   #      Logical Maximum (1023),      
        0x46, 0xFF, 0x03,   #      Physical Maximum (1023),     
        0x09, 0x2C,         #      Usage (2Ch),                 
        0x09, 0x2D,         #      Usage (2Dh),                 
        0x09, 0x2E,         #      Usage (2Eh),                 
        0x09, 0x2F,         #      Usage (2Fh),                 
        0x75, 0x10,         #      Report Size (16),            
        0x95, 0x04,         #      Report Count (4),            
        0x81, 0x02,         #      Input (Variable),            
        0xC0                #  End Collection                   
    ]
    
    # report example:
    #   LB1A2    L34
    #   RB2B4    R38
    #   LT4X1    SL1
    #   RT8Y8    ST2
    # 27  1 0  0   0 08 80 80 80 80 00 00 00 00 00 00 00 00 FF 00 00 00 00 02 00 02 00 02 00 02
    #    Dig Buttons    LS LS RS RS HR HL HU HD  X  A  B  Y LB RB LT RT
    #[ # each entry = 1 byte (ex: "\0\0" = 2 bytes (2B))
    #]

    def __init__(self, *args, **kwargs):
        self.State = namedtuple('State', 'bset1 bset2 hat x y z r hr hl hu hd bx ba bb by lb rb lt rt u4')
        self.format = struct.Struct('B' * 19 + '8s')
        self.neutral = self.State(
            #0x27,
            0x00, 0x00, # buttons
            0x08,
            0x00, 0x00, # LS
            0x00, 0x00, # RS
            0x00, 0x00, 0x00, 0x00, # HAT
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, # buttons (analog)
            bytes([0x00, 0x02, 0x00, 0x02, 0x00, 0x02, 0x00, 0x02]), # (not sure yet)
        ) 
        self.state = self.neutral

        # 0-15
        self.sdbuttons = dict((i, i) for i in range(0,16))
        # 0-5; x, y, z(rx), r(ry), hatrlud
        self.saxi = dict((i, i) for i in range(0,8))
        self.sabuttons = dict((i,i) for i in range(0,8))
        super(MNSD,self).__init__(*args, **kwargs)

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
        # TODO: simplify this
        #package = base64.b16decode('27'.replace(' ', ''))
        package = b''
        #package += struct.pack('B', self.state.u1)
        package += struct.pack('B', self.state.bset1)
        package += struct.pack('B', self.state.bset2)
        package += struct.pack('B', self.state.hat)
        # l&r sticks (0-255)
        package += struct.pack('B', self.state.x)
        package += struct.pack('B', self.state.y)
        package += struct.pack('B', self.state.z)
        package += struct.pack('B', self.state.r)
        package += struct.pack('B', self.state.hr)
        package += struct.pack('B', self.state.hl)
        package += struct.pack('B', self.state.hu)
        package += struct.pack('B', self.state.hd)
        package += struct.pack('B', self.state.bx)
        package += struct.pack('B', self.state.ba)
        package += struct.pack('B', self.state.bb)
        package += struct.pack('B', self.state.by)
        package += struct.pack('B', self.state.lb)
        package += struct.pack('B', self.state.rb)
        package += struct.pack('B', self.state.lt)
        package += struct.pack('B', self.state.rt)
        package += self.state.u4
        print(phexlify(package), end='\r')
        return package


    def transform_cc(self, lstate):
        ''' build capabilities class state from local state '''
        self.cstate = self.CState(
            lstate.bset1, lstate.bset2,
            lstate.x, lstate.r,
            lstate.y, lstate.z,
            lstate.hr, lstate.hl, lstate.hu, lstate.hd,
            lstate.bx, lstate.by, lstate.ba, lstate.bb,
            lstate.lb, lstate.rb, lstate.lt, lstate.rt,
        )
        return self.cstate

    def transform_local(self, cstate):
        ''' build local state from capabilities class state '''
        bhat = cstate.hr | cstate.hl << 1 | cstate.hu << 2 | cstate.hd << 3
        bhmap = {4:0,5:1,1:2,9:3,8:4,6:5,2:6,3:7}
        hat = bhmap.get(bhat, 8)
        self.state = self.State(
            cstate.bset1, cstate.bset2,
            hat,
            cstate.x, cstate.y,
            cstate.z, cstate.r,
            cstate.hr * 255, cstate.hl * 255, cstate.hu * 255, cstate.hd * 255,
            cstate.bx, cstate.by, cstate.ba, cstate.bb,
            cstate.lb, cstate.rb, cstate.lt, cstate.rt,
            self.state.u4,
        )
        return self.state


    def update_axis(self, id, value):
        aid = self.saxi.get(id, None)
        amap = {0:'x', 1:'y', 2:'z', 3:'r', 4:'hu', 5:'hr', 6:'hd', 7:'hl'}
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


class MNSDProfile(MNSD,Profile):
    pass

class MNSDPC(MNSD,Gamepad):
    # transforms
    bmap = {1:1, 2:4,3:3,4:2}
    def assign_device(self, device):
        self.device = device
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
        if self.raw:
            self.profile.recv_dev(self.state)
        else:
            cstate = self.transform_cc(self.state)
            self.profile.recv_dev(cstate)

if __name__ == '__main__':
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clean', default=False, action='store_true')
    parser.add_argument('-t', '--test', default=False, action='store_true')
    args = parser.parse_args()
    profile = MNSDProfile(path='/dev/hidg0')
    if args.clean:
        profile.clean()
        sys.exit()
    try:
        if args.test:
            con = MNSDPC()
            con.assign_profile(profile)
            # con.assign_device()
            # TODO: call con.listen() to receive new data to send to profile
            import hids
            s = hids.Stream('devices/magic-ns/dinput/stream')
            data = s.read(.01)
            for p in data:
                # print('%s (%s)' % (phexlify(p), len(p)), end='\r')
                con.read(p)
            sys.exit()
        profile.register()
    except SystemExit as e:
        pass
    except:
        _logger.warn(format_exc())
