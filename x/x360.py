#!/usr/bin/python3

from traceback import format_exc
from struct import *
from collections import namedtuple
import base64
import struct
import logging

from profiles import Profile
from devices import ClassicPCController
from common import phexlify

_logger = logging.getLogger(__name__ if __name__ != '__main__' else __file__)
logging.basicConfig()
_logger.setLevel(logging.INFO) # logging.getLevelName('INFO')

class X360():
    # TODO: work out state management
    
    name = 'X360'
    code = 'x360'
    raw = False

    usb_bcd = '0x020' # 02.00 # (USB2)
    vendor_id = '0x045e' # Sony Corp. # idVendor
    product_id = '0x028e' # Batoh Device / PlayStation 3 Controller # idProduct
    device_bcd = '0x0110' # 1.10 # bcdDevice
    manufacturer = '1' # 1 # iManufacturer
    product = '2' # 2 iProduct
    serial = '3' # iSerial
    configuration = 'Human Interface Device' # TODO: find out if there's anything relevant to put here
    max_power = '500' # 500mA # MaxPower
    
    # hid data
    protocol = '255' # bInterfaceProtocol
    subclass = '255' # bInterfaceSubClass
    report_length = '0' # wDescriptorLength (NOTE: this should mach lenth of resport_desc below)

    report_desc = []
    
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
        self.State = namedtuple('State', 'bset1 bset2 u3 x y z r hr hl hu hd bx ba bb by lb rb lt rt u4')
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
        super(X360,self).__init__(*args, **kwargs)

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
        package += struct.pack('B', self.state.u3)
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
        self.state = self.State(
            cstate.bset1, cstate.bset2,
            self.state.u3,
            cstate.x, cstate.y,
            cstate.z, cstate.r,
            cstate.hr, cstate.hl, cstate.hu, cstate.hd,
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


class X360Profile(X360,Profile):
    pass

class X360PC(X360,ClassicPCController):
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
        TODO: (in inherited device's state format (ie. ClassicPCController)
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
    from common import phexlify
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clean', default=False, action='store_true')
    parser.add_argument('-t', '--test', default=False, action='store_true')
    args = parser.parse_args()
    profile = X360Profile(path='/dev/hidg0')
    if args.clean:
        profile.clean()
        sys.exit()
    try:
        if args.test:
            con = X360PC()
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
