
# supported capability classes (intended to be inhereited for a variety of contexts)

# example flow:
# phys ps3 -> PS3(Gamepad) -> X360(Profile)

from collections import namedtuple
from argparse import Namespace
import struct

class Device(Namespace):
        pass

class Gamepad:
    # TODO: add some commonly shared functions (to ease implementation of cross-device feature)
    # supports the traditional PC-style (X360) controller layout
    # (may be extended in the future to support additional capabilities)
    # digital ABXY,RB,LB,RS,LS,Select,Start,Home
    # digital hat
    # analog LS, RS, LT, RT (shared Z(?))
    # leds: p1-p4, home
    # HD rumble/force feedback (TODO)
    # SEE: state for supported upper/lower limits/sensitivity
    # NOTE: devices and profiles may not support the level of sensitivity specified in this class
    #   or may not be able to support some features (limited selection of leds)
    #   however, they should map best they can (use full min/max range)
    def __init__(self, *args, **kwargs):
        super(Gamepad,self).__init__()

        self.CState = namedtuple('State', 'bset1 bset2 x y z r hr hl hu hd bx ba bb by lb rb lt rt')
        self.cformat = struct.Struct('B' * 18)
        self.cneutral = self.CState(
            0x00, 0x00, # buttons
            0x00, 0x00, # LS
            0x00, 0x00, # RS
            0x00, 0x00, 0x00, 0x00, # HAT
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, # buttons (analog)
        )
        self.cstate = self.cneutral
