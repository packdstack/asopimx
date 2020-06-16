#!/usr/bin/python3

# NOTE: hiddr-convert failed to parse this descriptor
# (parsable @ http://eleccelerator.com/usbdescreqparser/)

from traceback import format_exc
from struct import *
from collections import namedtuple
from datetime import datetime, timedelta
import base64
import struct
import logging

from asopimx.profiles import Profile
from asopimx.devices import Gamepad
from asopimx.tools import hz, phexlify, decode_bools, encode_bools
from asopimx.devices.jctalk import JCR, JCL, JCP, Device, Main
from asopimx.devices.swpro import SWPROProfile
from asopimx.scheduler import Scheduler

_logger = logging.getLogger(__name__ if __name__ != '__main__' else __file__)
logging.basicConfig()
_logger.setLevel(logging.INFO) # logging.getLevelName('INFO')

class SWJCP(JCP):
    # TODO: work out state management
    
    name = 'Switch Joycon Pair'
    code = 'swjcp'
    # transforms
    bmap = {3:2,2:1,0:0,1:3,6:5,23:6,22:4,11:10,10:11}



    usb_bcd = '0x020' # 02.00 # (USB2)
    vendor_id = '0x057e' # 1406  # idVendor
    product_id = '0x2009' # 8201 Batoh Device / PlayStation 3 Controller # idProduct
    device_bcd = '0x0113' # 1.19 # bcdDevice
    manufacturer = '0' # 1 # iManufacturer
    product = 'Joycon Pair' # 2 iProduct
    serial = '0' # iSerial
    configuration = 'Human Interface Device' # TODO: find out if there's anything relevant to put here
    max_power = '500' # 500mA # MaxPower
    
    # hid data
    protocol = '0' # bInterfaceProtocol
    subclass = '0' # bInterfaceSubClass

    # NOTE: currently mapped as a pro controller
    report_desc = [
    ] # TODO

    report_length = str(len(report_desc)) # wDescriptorLength

    def __init__(self, *args, **kwargs):
        super(SWJCP,self).__init__(*args, **kwargs)

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
        # TODO: update this (JCP has different state vars)
        #package = base64.b16decode('27'.replace(' ', ''))
        package = b''
        package += struct.pack('B', self.state.u1)
        package += struct.pack('B', self.state.bset1)
        package += struct.pack('B', self.state.bset2)
        package += struct.pack('B', self.state.h)
        package += struct.pack('B', self.state.u2)
        # l&r sticks (0-255)
        package += struct.pack('B', self.state.x)
        package += struct.pack('B', self.state.u3)
        package += struct.pack('B', self.state.y)
        package += struct.pack('B', self.state.u4)
        package += struct.pack('B', self.state.z)
        package += struct.pack('B', self.state.u5)
        package += struct.pack('B', self.state.r)
        #print(phexlify(package), end='\r')
        return package

    def transform_cc(self, lstate):
        ''' build capabilities class state from local state '''
        #self.cstate = self.cstate._replace(**{'bset1':lstate.bset1,'bset2':lstate.bset2})

        # adjust axi sensitivity
        axi = {'x': lstate.x, 'y':lstate.y, 'z':lstate.z,'r':lstate.r}
        # TODO: figure out calibration data (wotherwise deadzones will be huge)
        for k, v in axi.items():
            v = v >> 4 #/ 16
            if v <= 120:
               axi[k] = max(int(((v - 120) * 3) + 120), 0) 
            elif v >= 134:
               axi[k] = min(int(((v - 134) * 3) + 134), 255)
            else:
                axi[k] = v
        # flip y & r axi # (and adjust center)
        axi['y'] = 127 - (axi['y'] - 127) # + 36
        axi['r'] = 127 - (axi['r'] - 127) # - 24
        # add dead zones
        # (should really only be used for loose sticks, not calibration adjustment)
        ypct = 42
        rpct = 32
        axi['y'] = 127 if 127 - ypct < axi['y'] < 127 + ypct else axi['y']
        axi['r'] = 127 if 127 - rpct < axi['r'] < 127 + rpct else axi['r']
        # ensure they're within boundaries
        axi['y'] = max(0, min(255, axi['y']))
        axi['r'] = max(0, min(255, axi['r']))
        bset1 = lstate.bset[0]
        bset2 = lstate.bset[1]
        bset3 = lstate.bset[2]
        bstates = []
        btransform = []
        for bs in [bset1, bset2, bset3]:
            bstates.extend(decode_bools(bs, 8))
            btransform.extend(decode_bools(bs, 8))
        # remap buttons 1-4
        for k, v in self.bmap.items():
            btransform[v] = bstates[k]
        bset1=encode_bools(btransform[:8])
        bset2=encode_bools(btransform[8:-8])
        bset3=encode_bools(btransform[-8:])
        self.cstate = self.CState(
            bset1, bset2,
            axi['x'], axi['y'],
            axi['z'], axi['r'],
            # r l u d
            btransform[18], btransform[19], btransform[17], btransform[16], # hat
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
 
        self.state = self.State(
            self.state.u1,
            bset1, cstate.bset2,
            0x08, # TODO: hat
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


class SWJCPProfile(SWJCP,Profile):
    pass

class SWJCPPC(SWJCP,Gamepad):
    def __init__(self, loop=None):
        super(SWJCPPC, self).__init__(loop=loop)

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
        self.cstate = self.transform_cc(self.lstate)
        self.profile.recv_dev(self.cstate)
    def listen(self):
        #from threading import Timer
        #self.t = Timer(0.5, self.poll_state)
        #self.t.start()
        #self.s = Timer(0.5, self.send_profile)
        #self.s.start()
        # TODO: handle timeouts
        import time
        target_speed = timedelta(seconds=hz(120))
        race = False
        scheduler = Scheduler()
        last = datetime.now()
        while True:
            scheduler.run()
            self.observe()
            self.send_profile()
            if race:
                continue
            now = datetime.now()
            delta = now - last
            if delta > target_speed:
                _logger.warn(
                    'Falling behind: %s (%shz) / Target: %s (%shz)',
                    delta.total_seconds(), hz(delta.total_seconds()),
                    target_speed.total_seconds(), hz(target_speed.total_seconds()),
                )
                race = True
                # target_speed = timedelta(seconds=hz(60))
            else:
                time.sleep((target_speed - delta).total_seconds())
            last = datetime.now() # sleeping means we'll be a little slower

if __name__ == '__main__':
    import argparse
    import sys
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
            m = Main()
            con = SWJCPPC()
            con.assign_profile(profile)
            m.find_devices(pair=False)
            for d in m.found:
                con.assign_device(d)
                #con.assign_device(d.devinfo.path)
            con.listen()
            #m.loop.run_forever()
            sys.exit()
        profile.register()
    except SystemExit as e:
        pass
    except:
        _logger.warn(format_exc())

