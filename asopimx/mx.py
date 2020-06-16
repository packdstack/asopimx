#!/usr/bin/python3

import hid
from traceback import format_exc
import time
import logging

_logger = logging.getLogger(__file__ if __name__ == '__main__' else __name__)

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

    def find_devices(self, pair=True):
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
                print('%s Found! (%s / %s)' % (d.product_string, d.serial_number, d.path))
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
                        print('pairing devices!')
                        # TODO: test this for more than one composite device!
                        # (it probably doesn't work)
                        d = CDev()
                        print(d)
                        for K, sd in fitems.items():
                            ad = sd[0]
                            d.assign_device(ad)
                            removal = set([ad,])
                            new = list(set(new) - removal)
                        new.append(d)
                    except Exception as e:
                        _logger.warn(format_exc())
                        _logger.warn(e)

        self.found.extend(new)

    def disable_wifi(self):
        if not self.wl_blocked:
            self.wl0.block()


    def run(self):
        from asopimx.tools.rfkill import wlan
        from asopimx.ui.af12x64oled import AsopiUI as UI
        from asopimx.scheduler import Scheduler
        self.wl0 = wlan.first()
        self.wl_blocked = self.wl0.softblock # initial state
        self.scheduler = Scheduler()
        self.ui = UI()
        self.ui.start()
        while True:
            try:
                self.scheduler.run()
                while not self.found:
                    self.find_devices()
                    time.sleep(1)
                if not self.wl_blocked and not self.found:
                    self.wl0.unblock() # re-enable wifi
                if len(self.found) > 1:
                    print('Warning: One device at at time.')
                con = self.found[0]
                con.assign_profile(self.profile)
                con.listen()
            except AttributeError as e:
                _logger.warn(format_exc())
            except OSError as e:
                _logger.warn(e)
            except SystemExit as e:
                self.ui.clear()
                raise
            finally:
                if not self.wl_blocked:
                    self.wl0.unblock()

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
        from tools import phexlify
        parser = argparse.ArgumentParser(
            description='if no arguments specified, registers profile'
        )
        parser.add_argument(
            '-r', '--register', default=False, action='store_true',
        )
        parser.add_argument('-t', '--test', default=False, action='store_true')
        parser.add_argument('-c', '--clean', default=False, action='store_true')
        parser.add_argument(
            '-p', '--profile', default='swpro',
            help='Capability profile.'
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

        if args.register:
            self.profile.register()
        try:
            if args.test:
                self.run()
        except SystemExit as e:
            pass
        except:
            _logger.warn(format_exc())
        finally:
            if args.clean:
                self.profile.clean()


if __name__ == '__main__':
    # TODO: add (performance) profiling support
    a = AsopiMX()
    a.main()

