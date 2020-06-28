#!/usr/bin/python3

import hid # we assume this is just uses libusb; hidraw, even when installed, can't be specified
from traceback import format_exc
import time
import logging

_logger = logging.getLogger(__file__ if __name__ == '__main__' else __name__)

from asopimx.tools.btctl import Btctl
# enumerate supported devices & profiles
# TODO: automate this
from asopimx.devices import Device
from asopimx.devices.mnsd import MNSDProfile, MNSDPC
from asopimx.devices.ps3 import PS3Profile, PS3Pad
from asopimx.devices.swpro import SWPROProfile, SWPROPC
from asopimx.devices.swjc import SWJCPProfile, SWJCPPC, JCL, JCR
devices = [
    MNSDPC, SWPROPC, PS3Pad,
]
composite_devices = [
    (SWJCPPC, [JCL, JCR])
]
profiles = [
    MNSDProfile, SWPROProfile, PS3Profile, # SWJCPProfile,
]
prof_code_map = dict([(p.code, p) for p in profiles])

class AsopiMX():
    def __init__(self):
        self.lasts = {}
        self.count = 0
        self.refresh = .05

        self.found = [] # devices found
        self.pmap = {} # device product map
        self.cpmap = {} # composite device product map
        for cls in devices:
            for p in cls.products:
                self.pmap[p] = cls
        for ccls, cdvcs in composite_devices:
            for cls in cdvcs:
                for p in cls.products:
                    self.cpmap[p] = cls
        self.dnames = {d.product for d in devices}

    def find_bt_devices(self, pair=True):
        # TODO: mesh these with hid devices somehow
        new = []
        _logger.info('getting bt devices')
        ds = self.btctl.get_devices()
        _logger.info('filtering %s devices', len(ds))
        #ds = [d for d in ds if d.name in self.dnames] # this takes longer than is should
        ds = tuple(filter(lambda x: x.name in self.dnames, ds))
        from subprocess import check_output
        import re
        from lxml import etree
        for d in ds:
            # look for certain classes and product names
            # 0x00002508
            if d.name in self.dnames: # make sure it's really what we're looking for
                _logger.debug('checking %s',  d.name)
                try:
                    self.btctl.connect(d)
                except: # probably not there
                    #_logger.warning(format_exc())
                    _logger.warning('%s: unable to connect; skipping', d.name)
                    continue
                try:
                    sdps = check_output(['sdptool','records',d.address]) # "human-readable"!
                    sdps = '<records>' + re.sub('<\?xml.*\?>?', '', sdps).strip() + '</records>'
                    sdps = etree.fromstring(sdps)
                    # get vendors for listed services
                    vendors = e.xpath("//attribute[@id='0x0201']")
                    vendors = [v.xpath('./uint16')[0].values()[0] for v in vendors]
                    vendors = [int(v, 16) for v in vendors]
                    # get products for listed services
                    products = e.xpath("//attribute[@id='0x0202']")
                    products = [v.xpath('./uint16')[0].values()[0] for v in products]
                    products = [int(v, 16) for v in products]
                    vp_keys = [(v, p) for v in vendors for v in products]
                    matches = set(vcp_keys) & set(self.cpmap.keys())
                    matches = matches or set(vcp_keys) & set(self.pmap.keys())
                    if matches:
                        key = matches[0]
                        dev = d
                        d = Device({ # TODO: fill device with expected info
                            'vendor_id': key[0],
                            'product_id': key[1],
                            'path': d.path,
                            'product_string': 'tbd',
                            'serial_number': 'tbd',
                            'dev': dev,
                        })
                    else:
                        continue
                except Exception as e:
                    _logger.warning(format_exc())
                    _logger.warning('BT check failed: %s', e)
                    continue
            else:
                continue

            if key in self.cpmap.keys() or key in self.pmap.keys():
                claimed = False
                for f in self.found:
                    if f.claimed(d):
                        claimed = True
                        break # already found
                if claimed:
                    continue
                _logger.info('%s Found! (%s / %s)' % (d.product_string, d.serial_number, d.path))
                self.btctl.pair(d.dev)
                self.btctl.trust(d.dev)
                #self.disable_wifi() # no wifi, please

                Dcls = self.cpmap.get(key, self.pmap.get(key))
                newd = Dcls(d) # , self.loop)
                new.append(newd)
                return


        if pair and new and (len(self.found) > 1 or len(new) > 1):
            found_new = self.found + new
            for CDev, cdvcs in composite_devices:
                fitems = {}
                for dvc in cdvcs:
                    filtered = filter(lambda x: isinstance(x, dvc), found_new)
                    fitems[dvc] = [f for f in filtered]
                if len(fitems) == len(cdvcs):
                    try:
                        _logger.info('pairing devices!')
                        # TODO: test this for more than one composite device!
                        # (it probably doesn't work)
                        d = CDev()
                        _logger.debug(d)
                        for K, sd in fitems.items():
                            ad = sd[0]
                            d.assign_device(ad)
                            removal = set([ad,])
                            new = list(set(new) - removal)
                        new.append(d)
                    except Exception as e:
                        _logger.warning(format_exc())
                        _logger.warning(e)

        self.found.extend(new)

    def find_hid_devices(self, pair=True):
        new = []
        ds = hid.enumerate()
        for d in ds:
            d = Device(**d)
            vid = d.vendor_id
            pid = d.product_id
            key = (vid, pid)
            if key in self.cpmap.keys() or key in self.pmap.keys():
                claimed = False
                for f in self.found:
                    if f.claimed(d):
                        claimed = True
                        break # already found
                if claimed:
                    continue
                _logger.info('%s Found! (%s / %s)' % (d.product_string, d.serial_number, d.path))
                self.disable_wifi() # no wifi, please
                dev = hid.device()
                dev.open_path(d.path)
                d.dev = dev

                Dcls = self.cpmap.get(key, self.pmap.get(key))
                newd = Dcls(d) # , self.loop)
                new.append(newd)


        if pair and new and (len(self.found) > 1 or len(new) > 1):
            found_new = self.found + new
            for CDev, cdvcs in composite_devices: 
                fitems = {}
                for dvc in cdvcs:
                    filtered = filter(lambda x: isinstance(x, dvc), found_new)
                    fitems[dvc] = [f for f in filtered]
                if len(fitems) == len(cdvcs):
                    try:
                        _logger.info('pairing devices!')
                        # TODO: test this for more than one composite device!
                        # (it probably doesn't work)
                        d = CDev()
                        _logger.debug(d)
                        for K, sd in fitems.items():
                            ad = sd[0]
                            d.assign_device(ad)
                            removal = set([ad,])
                            new = list(set(new) - removal)
                        new.append(d)
                    except Exception as e:
                        _logger.warning(format_exc())
                        _logger.warning(e)

        self.found.extend(new)

    def disable_wifi(self):
        if not self.skip_wifi and not self.wl_blocked: # wifi was initially on
            _logger.info('Disabling WIFI')
            self.wl0.block()

    def enable_wifi(self):
        if not self.skip_wifi and not self.wl_blocked: # wifi was initially on
            _logger.info('Enabling WIFI')
            self.wl0.unblock()


    def run(self):
        from asopimx.tools.rfkill import wlan
        from asopimx.ui.af12x64oled import AsopiUI as UI
        from asopimx.scheduler import Scheduler
        self.wl0 = wlan.first()
        self.wl_blocked = self.wl0.softblock # initial state
        self.scheduler = Scheduler()
        self.btctl = Btctl()
        try:
            self.ui = UI()
            self.ui.start()
        except Exception as e:
            _logger.warning('Unable to start ui; ignoring. (%s)', e)
            self.ui = None
        scanning = False
        while True:
            try:
                self.scheduler.run()
                if not scanning:
                    self.btctl.start_scan()
                    scanning = True
                while not self.found:
                    self.find_hid_devices()
                    if not self.found:
                        self.find_bt_devices()
                    time.sleep(1)
                if self.found:
                    self.btctl.stop_scan()
                    scanning = False
                if not self.wl_blocked and not self.found:
                    self.enable_wifi() # re-enable wifi
                if len(self.found) > 1:
                    _logger.warning('Multiple devices found; only one device at at time is supported.')
                con = self.found[0]
                con.assign_profile(self.profile)
                con.listen()
            except AttributeError as e:
                _logger.warning(format_exc())
            except OSError as e:
                _logger.warning(format_exc())
                _logger.warning(e)
            except SystemExit as e:
                if not self.ui is None:
                    self.ui.clear()
                raise
            finally:
                if not self.wl_blocked:
                    self.enable_wifi()

            self.found = [] # go back to finding devices
            time.sleep(1)
            # TODO: add support for stream tests
            #import hids
            #s = hids.Stream('devices/magic-ns/dinput/stream')
            #data = s.read(.01)
            #for p in data:
            #    # print('%s (%s)' % (phexlify(p), len(p)), end='\r')
            #    con.read(p)

    def main(self):
        import argparse
        import sys
        from asopimx.tools import phexlify

        # make sure we have relevant modules loaded
        try:
            import subprocess
            if subprocess.check_call(['/sbin/modprobe','dwc2','libcomposite']) != 0:
                _logger.error('Unabled to load relevant kernel modules Exiting.')
                sys.exit()
        except Exception as e:
            _logger.error('Unabled to load relevant kernel modules: %s', e)
            sys.exit(1)


        parser = argparse.ArgumentParser(
            description='if no arguments specified, registers a profile and starts listening for supported devices to connect'
        )
        parser.add_argument(
            '-r', '--register', default=False, action='store_true',
            help='Register a profile (what the host system will see AsopiMX is capable of once connected)'
        )
        parser.add_argument('-t', '--test', default=False, action='store_true')
        parser.add_argument('-c', '--clean', default=False, action='store_true')
        parser.add_argument('-w', '--wifi', default=False, action='store_true')
        parser.add_argument(
            '-p', '--profile', default='swpro',
            help='Capability profile to register'
        )
        parser.add_argument(
            '-s', '--supported', default=False, action='store_true',
            help='List supported devices & profiles'
        )


        args = parser.parse_args()
        if args.supported:
            print([c for c in prof_code_map.keys()])
            sys.exit()
        if not args.test and not args.register and not args.clean:
           args.test = args.register = args.clean = True

        try:
            self.profile = prof_code_map.get(args.profile)(path='/dev/hidg0')
        except Exception as e:
            print(
                'Unable to load requested profile (%s): %s' % (args.profile, e)
            )

        self.skip_wifi = args.wifi
        try:
            if args.register:
                self.profile.register()
            if args.test:
                self.run()
        except SystemExit as e:
            pass
        except PermissionError as e:
            _logger.error(e)
            print('Permissions failed. Running as root?')
        except:
            _logger.warning(format_exc())
        finally:
            if args.clean:
                try:
                    self.profile.clean()
                except (FileNotFoundError, PermissionError) as e:
                    _logger.error(e)


if __name__ == '__main__':
    # TODO: add (performance) profiling support
    a = AsopiMX()
    a.main()

