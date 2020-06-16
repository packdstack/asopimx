#!/usr/bin/python

# Multiplexing via legacy js interface (kept for posterity)
# Thanks to rdb for his quick example implementation!

# SEE: https://www.kernel.org/doc/Documentation/input/joystick-api.txt 

import os, struct, array
from fcntl import ioctl
from struct import *
from collections import namedtuple
import base64
import logging

_logger = logging.getLogger(__name__ if __name__ != '__main__' else 'jsmx')

class JSMX():
    # Constants (see linux/input.h)
    axis_names = {
        0x00 : 'x',
        0x01 : 'y',
        0x02 : 'z',
        0x03 : 'rx',
        0x04 : 'ry',
        0x05 : 'rz',
        0x06 : 'trottle',
        0x07 : 'rudder',
        0x08 : 'wheel',
        0x09 : 'gas',
        0x0a : 'brake',
        0x10 : 'hat0x',
        0x11 : 'hat0y',
        0x12 : 'hat1x',
        0x13 : 'hat1y',
        0x14 : 'hat2x',
        0x15 : 'hat2y',
        0x16 : 'hat3x',
        0x17 : 'hat3y',
        0x18 : 'pressure',
        0x19 : 'distance',
        0x1a : 'tilt_x',
        0x1b : 'tilt_y',
        0x1c : 'tool_width',
        0x20 : 'volume',
        0x28 : 'misc',
    }

    button_names = {
        0x120 : 'trigger',
        0x121 : 'thumb',
        0x122 : 'thumb2',
        0x123 : 'top',
        0x124 : 'top2',
        0x125 : 'pinkie',
        0x126 : 'base',
        0x127 : 'base2',
        0x128 : 'base3',
        0x129 : 'base4',
        0x12a : 'base5',
        0x12b : 'base6',
        0x12f : 'dead',
        0x130 : 'a',
        0x131 : 'b',
        0x132 : 'c',
        0x133 : 'x',
        0x134 : 'y',
        0x135 : 'z',
        0x136 : 'tl',
        0x137 : 'tr',
        0x138 : 'tl2',
        0x139 : 'tr2',
        0x13a : 'select',
        0x13b : 'start',
        0x13c : 'mode',
        0x13d : 'thumbl',
        0x13e : 'thumbr',
    
        0x220 : 'dpad_up',
        0x221 : 'dpad_down',
        0x222 : 'dpad_left',
        0x223 : 'dpad_right',
    
        # XBox 360 controller uses these codes.
        0x2c0 : 'dpad_left',
        0x2c1 : 'dpad_right',
        0x2c2 : 'dpad_up',
        0x2c3 : 'dpad_down',
    }

    @staticmethod
    def list_devices():
        print('Available devices:')
        
        for fn in os.listdir('/dev/input'):
            if fn.startswith('js'):
                print('  /dev/input/%s' % (fn))
    
    @staticmethod
    def encode_bools(bool_lst):
        res = 0
        for i, bval in enumerate(bool_lst):
            res += int(bval) << i
        return res
    
    @staticmethod
    def decode_bools(intval, bits):
        res = []
        for bit in xrange(bits):
            mask = 1 << bit
            res.append((intval & mask) == mask)
        return res
    
    
    def __init__(self):
        self.axis_states = {}
        self.button_states = {}
        self.axis_map = []
        self.button_map = []

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
        
        # Open the joystick device.
        fn = '/dev/input/js0'
        print('Opening %s...' % fn)
        self.jsdev = open(fn, 'rb')
        
        # Get the device name.
        #buf = bytearray(63)
        buf = array.array('c', ['\0'] * 64)
        ioctl(self.jsdev, 0x80006a13 + (0x10000 * len(buf)), buf) # JSIOCGNAME(len)
        js_name = buf.tostring()
        print('Device name: %s' % js_name)
        
        # Get number of axes and buttons.
        buf = array.array('B', [0])
        ioctl(self.jsdev, 0x80016a11, buf) # JSIOCGAXES
        num_axes = buf[0]
        
        buf = array.array('B', [0])
        ioctl(self.jsdev, 0x80016a12, buf) # JSIOCGBUTTONS
        num_buttons = buf[0]
        
        # Get the axis map.
        buf = array.array('B', [0] * 0x40)
        ioctl(self.jsdev, 0x80406a32, buf) # JSIOCGAXMAP
        
        for axis in buf[:num_axes]:
            axis_name = self.axis_names.get(axis, 'unknown(0x%02x)' % axis)
            self.axis_map.append(axis_name)
            self.axis_states[axis_name] = 0.0
        
        # Get the button map.
        buf = array.array('H', [0] * 200)
        ioctl(self.jsdev, 0x80406a34, buf) # JSIOCGBTNMAP
        
        for btn in buf[:num_buttons]:
            btn_name = self.button_names.get(btn, 'unknown(0x%03x)' % btn)
            self.button_map.append(btn_name)
            self.button_states[btn_name] = 0
        
        print('%d axes found: %s' % (num_axes, ', '.join(self.axis_map)))
        print('%d buttons found: %s' % (num_buttons, ', '.join(self.button_map)))

        # tried to use structs, but reverted back to hex-manipulation
        # due to sizing issues (and endian-ness was mixing everything up)
        self.dformat = 'bbBBbbBBBBihiqqQ'
        self.State = namedtuple('State', 'u1 u2 bset1 bset2 u3 u4 x y z r u5 hu hr hd hl u6 u7 u8 u9 u10 u11')
        self.state = self.State(
            1, 0,
            0, 0,
            0, 0,
            0, 0, 0, 0,
            0,
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0,
        )
        print(str(self.state.u6))
        # \x1\0\xff\x2\0\0\x83\x7d\x81\x80
        # \0\0\0\0\0\0\0
        # \0\0\0\0\0\0\0\0
        # \0\0\0\0\x2\xee\x12\0
        # \0\0\0\x12\xf8\x77\0\0
        # \x2\x7\x1\xee\x1\x94\x1\xd7

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
        package += struct.pack('H', self.state.bset1)
        print(self.state.x)
        # 16-buttons (binary)
        package += base64.b16decode('00 00'.replace(' ', ''))
        # l&r sticks (0-255)
        package += struct.pack('B', self.state.x)
        package += struct.pack('B', self.state.y)
        package += struct.pack('B', self.state.z)
        package += struct.pack('B', self.state.r)
        package += base64.b16decode('00 00 00 00'.replace(' ', ''))
        #package += base64.b16decode('00 00 00 83 7D 81 80 00 00 00 00 00 00'.replace(' ', ''))
        # hat (0-255)
        package += struct.pack('B', self.state.hu)
        package += struct.pack('B', self.state.hr)
        package += struct.pack('B', self.state.hd)
        package += struct.pack('B', self.state.hl)
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
        print(len(package))
        return package

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

    def send_event(self):
        s = self.repack()
        print(repr(s))
        with open('/dev/hidg0', 'wb') as f:
            f.write(s)

    def mix(self):
        # send initial state
        self.send_event()
        
        # event loop
        while True:
            self.send_event()
            evbuf = self.jsdev.read(8)
            if evbuf:
                time, value, type, number = struct.unpack('IhBB', evbuf)
        
                if type & 0x80:
                     print("(initial)")
        
                if type & 0x01:
                    button = self.button_map[number]
                    state = self.update_button(number, value)
                    self.send_event()
                    if button:
                        self.button_states[button] = value
                        if value:
                            print("%s pressed" % (button))
                        else:
                            print("%s released" % (button))
        
                if type & 0x02:
                    axis = self.axis_map[number]
                    print(number)
                    if axis:
                        self.update_axis(number, value)
                        self.send_event()
                        fvalue = value / 32767.0
                        self.axis_states[axis] = fvalue
                        print("%s: %.3f" % (axis, fvalue))

if __name__ == '__main__':
    # TODO: do something more useful
    JSMX.list_devices()
    jsmx = JSMX()
    jsmx.mix()
