#!/usr/bin/python3

# Supplies base classes for implementing phys device support and profiles to mimic them
# NOTE: they're often implemented together; they share much of the same data,
#   but serve different sides of the conversation
# Profiles are intended to support specific device capability classes (SEE: devices.py)

import os
from os import path
import errno
from subprocess import check_output
from traceback import format_exc
import shutil
from struct import *
from collections import namedtuple
import base64
import logging
from asopimx.tools import *

_logger = logging.getLogger(__file__ if __file__ != '__main__' else 'ps3.py')
logging.basicConfig()
_logger.setLevel(logging.INFO) # logging.getLevelName('INFO')

class Profile:
    # inheritors should fill these out with whatever's appropriate for them
    raw = False
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
    
    base_dir = '/sys/kernel/config/usb_gadget'
    mx_dir = path.join(base_dir, 'piconmx')
    config_dir = path.join(mx_dir, 'configs/c.1/')
    config_str_dir = path.join(config_dir, 'strings/0x409')

    report_desc = []

    def __init__(self, path=None):
        self.fd = None
        if path is None:
            # attempt to register
            pass
        else: # we're already registered?
            # TODO: check to see if this path is legit
            self.path = path

    def clean(self):
        # TODO: make this more pythonic
        # disable gadget
        write('', path.join(self.mx_dir, 'UDC'))
        os.system('rm %s/configs/*.*/*' % self.mx_dir)
        # remove configuration string directories
        os.system('rmdir %s/configs/*/strings/*' % self.mx_dir)
        # remove configurations
        os.system('rmdir %s/configs/*' % self.mx_dir)
        # remove functions (modules aren't unloaded)
        os.system('rmdir %s/functions/*' % self.mx_dir)
        # remove gadget string directories
        os.system('rmdir %s/*' % self.config_str_dir)
        # remove gadget
        os.system('rmdir ' + self.mx_dir)
    
    def register(self):
        if os.path.isdir(self.mx_dir):
            self.clean()
        _logger.info(self.mx_dir)
        makedirs(self.mx_dir)
        write(self.vendor_id, path.join(self.mx_dir, 'idVendor'))
        write(self.product_id, path.join(self.mx_dir, 'idProduct'))
        write(self.device_bcd, path.join(self.mx_dir, 'bcdDevice'))
        write(self.usb_bcd, path.join(self.mx_dir, 'bcdUSB'))
        desc_dir = path.join(self.mx_dir, 'strings/0x409')
        makedirs(desc_dir)
        write(self.serial, path.join(desc_dir, 'serialnumber'))
        write(self.manufacturer, path.join(desc_dir, 'manufacturer'))
        write(self.product, path.join(desc_dir, 'product'))
        makedirs(self.config_str_dir)
        write(self.configuration, path.join(self.config_str_dir, 'configuration'))
        write(self.max_power, path.join(self.config_dir, 'MaxPower'))
        # hid stuff
        hid_dir = path.join(self.mx_dir, 'functions/hid.usb0')
        makedirs(hid_dir)
        write(self.protocol, path.join(hid_dir, 'protocol'))
        write(self.subclass, path.join(hid_dir, 'subclass'))
        write(self.report_length, path.join(hid_dir, 'report_length'))
        write(bytearray(self.report_desc), path.join(hid_dir, 'report_desc'))
        os.symlink(hid_dir, path.join(self.config_dir, 'functions'))
        write(check_output(['ls','/sys/class/udc']), path.join(self.mx_dir, 'UDC'))
        # TODO: figure out which device we are (path to send/receive data)
        # for now, assume we're the only one (/dev/hidg0)
        self.path = '/dev/hidg0'

    def repack(self): # should be overidden to return profile's HID report ready to send
        return ''

    def recv_dev(self, state):
        ''' receive state from device '''
        #TODO: translate supported capability class state to profile
        if self.raw: # raw state; same device pass-through
            self.state = state
        else:
            self.cstate = state
            self.state = self.transform_local(self.cstate)
        self.send_event()

    def send_event(self):
        ''' repack state and send to host '''
        s = self.repack()
        #print(repr(s))
        #with open(self.path, 'wb') as f:
        #    f.write(s)
        if self.fd is None:
            # wait until device's created
            # (won't work if we create the file ourselves)
            if not path.exists(self.path):
                _logger.warn('%s not ready; discarding event', self.path)
                return
            else:
                self.fd = open(self.path, 'wb')

        self.fd.write(s)
        self.fd.flush()
        #os.fsync(self.fd)


if __name__ == '__main__':
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clean', default=False, action='store_true')
    args = parser.parse_args()
    dev = Profile()
    if args.clean:
        dev.clean()
        sys.exit()
    try:
        dev.register()
    except:
        _logger.warn(format_exc())
