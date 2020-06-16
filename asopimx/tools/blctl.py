#!/usr/bin/python3

''' bluetooth control interface
nullp0tr put so much work into making bluew great,
might as well try to use as much of it as we can!

NOTE: We can't tell if a device is trying to pair or not.

    This becomes a problem when the device attempts to pair again.
    Others work around this by having an explicit pairing mode.

    Alternatively, you can try to pair with disconnected devices
    to see if they'll pair again.
'''

import logging
#import threading
import time
from typing import List, Optional, Callable  # pylint: disable=W0611
import dbus

_logger = logging.getLogger(__name__)

import bluew
from bluew.dbusted.interfaces import BluezInterfaceError as BIError
from bluew.dbusted.interfaces import (
    BluezGattCharInterface,
    BluezAgentManagerInterface,
    BluezObjectInterface,
    BluezAdapterInterface,
    BluezDeviceInterface,
    Controller,
    Device,
    BLECharacteristic,
    BLEService,
    dbus_object_parser
)

from bluew.errors import (
    BluewError,
    NoControllerAvailable,
    ControllerSpecifiedNotFound,
    PairError,
    DeviceNotAvailable,
    ControllerNotReady,
    ReadWriteNotifyError,
    InvalidArgumentsError
)

from bluew.dbusted.decorators import (
    mac_to_dev,
    check_if_available,
    check_if_connected,
    check_if_not_paired,
    handle_errors
)

class BIO(BluezObjectInterface):
    pass
        

class Btctl:
    def __init__(self):
        self.name = 'Bluew'
        self.version = '0.1'
        self._bus = dbus.SystemBus()
        self.cntl = None # specify a controller
        self._init_cntl()

    # TODO: add enter/exit logic

    def _init_cntl(self):
        ctls = self.get_controllers()
        if self.cntl is None: # pick one
            if not ctls:
                raise NoControllerAvailable()
            else:
                self.cntl = self._strip_cntl_path(ctls[0])
        else: # make sure we can find it
            paths = list(map(self._strip_cntl_path, ctls))
            if self.cntl not in paths:
                raise ControllerSpecifiedNotFound()
            # else: we're good

    def start_scan(self) -> None:
        bia = BluezAdapterInterface(self._bus, self.cntl)
        bia.start_discovery()

    def stop_scan(self) -> None:
        bia = BluezAdapterInterface(self._bus, self.cntl)
        bia.stop_discovery()

    # for those w/ diff terms

    def start_discovery(self) -> None:
        self.start_scan()

    def stop_discovery(self) -> None:
        self.stop_scan()

    @property
    def devices(self):
        bio = BIO(self._bus)
        return bio.get_devices()

    # some convenience functions (use x.devices to save round-trips)

    @property
    def paired_devices(self):
        return tuple(filter(lambda x: x.paired, self.devices))

    @property
    def connected_devices(self):
        return tuple(filter(lambda x: x.connected, self.devices))

    @property
    def disconnected_devices(self):
        return tuple(filter(lambda x: x.paired and not x.connected, self.devices))

    @property
    def new_devices(self):
        return tuple(filter(lambda x: not x.paired, self.devices))

    def dev_to_path(self, dev):
        if isinstance(dev, bluew.device.Device):
            if dev.paired:
                print('altready paired...')
            #    self.remove(dev)
            mac = ('/dev:%s' % dev.address).replace(':', '_')
        else:
            mac = dev
        return mac

    def pair(self, dev) -> None:
        mac = self.dev_to_path(dev)
        bid = BluezDeviceInterface(self._bus, mac, self.cntl)
        did = '/org/bluez/' + self.cntl + mac
        print(did)
        bo = self._bus.get_object('org.bluez', did)
        print(bo)
        dif = dbus.Interface(bo, 'org.bluez.Device1')
        prop = dbus.Interface(bo, 'org.freedesktop.DBus.Properties')
        print(dif)
        dif.Pair() # pair
        dif.Connect() # connect
        prop.Set('org.bluez.Device1', 'Trusted', True) # trust
        print(bid.dev)
        print('pairing')
        #bid.pair_device()
        #paired = self.is_device_paired(dev.path)
        #if not paired:
        #    raise PairError(self.name, self.version)

    def is_device_paired(self, path) -> bool:
        devices = self.devices
        filtered = [filter(lambda x: path in x.path, devices)]
        filtered = [filter(lambda x: path in x.paired, filtered)]
        return bool(filtered)

    def trust(self, dev) -> None:
        mac = self.dev_to_path(dev)
        bid = BluezDeviceInterface(self._bus, mac, self.cntl)
        did = '/org/bluez/' + self.cntl + mac
        bo = self._bus.get_object('org.bluez', did)
        dif = dbus.Interface(bo, 'org.bluez.Device1')
        prop = dbus.Interface(bo, 'org.freedesktop.DBus.Properties')
        prop.Set('org.bluez.Device1', 'Trusted', True) # trust

    def connect(self, dev) -> None:
        mac = self.dev_to_path(dev)
        bid = BluezDeviceInterface(self._bus, mac, self.cntl)
        did = '/org/bluez/' + self.cntl + mac
        print(did)
        bo = self._bus.get_object('org.bluez', did)
        print(bo)
        dif = dbus.Interface(bo, 'org.bluez.Device1')
        print(dif)
        # connect
        dif.Connect()

    def remove(self, dev) -> None:
        # TODO: device ops want dev.path, not (strictly) mac
        # (BLuezAdapterInterface tries too hard)
        # example: /org/bluez/hci0/dev_00_00_00_00_00_00 
        mac = self.dev_to_path(dev)
        print('removing %s' % mac)
        print(self.cntl)
        bia = BluezAdapterInterface(self._bus, self.cntl)
        bia.remove_device(mac)

    def get_controllers(self) -> List[Controller]:
        """
        Overriding EngineBluew's get_controllers method.
        :return: List of controllers available.
        """
        bio = BluezObjectInterface(self._bus)
        return bio.get_controllers()

    @staticmethod
    def _strip_cntl_path(cntl):
        path = getattr(cntl, 'Path')
        return path.replace('/org/bluez/', '')

if __name__ == '__main__':
    import time
    logging.basicConfig()
    b = Btctl()
    print(b.devices)
    print(b.paired_devices)
    print(b.connected_devices)
    disconnected = b.disconnected_devices
    failed_disconnected = []
    for d in b.connected_devices:
        print(d.__dict__)
    for d in disconnected:
        print(d.__dict__)
        # TODO: don't block here; we could have a lot of devices to check
        try:
            # NOTE: this appears to work even while device
            #    is in pairing mode (if it hasn't been paired elsewhere)
            b.connect(d)
            print('Connected to known device: %s' % d.name) 
        except dbus.exceptions.DBusException as e:
            name = e.get_dbus_name()
            message = e.get_dbus_message()
            if name == 'org.bluez.Error.Failed' and \
                    message == 'Input/output error':
                _logger.warn(
                    "Known device unavailable: %s",
                    d.name
                )
                failed_disconnected.append(d)
            else:
                raise
        # example modalias for paired device:  usb:v057Ep2009d0001
    b.start_scan()
    time.sleep(10) # give the device some time to find something
    new_devices = b.new_devices
    print(new_devices)
    for d in new_devices:
        if d.name in ['Pro Controller', 'Joy-Con (R)', 'Joy-Con (L)']:
            # TODO: check mac
            print('Pro Con found!  pairing')
            b.pair(d)
    b.stop_scan()
    not_found = set(failed_disconnected) - set(b.paired_devices)
    # re-add not found (if they come back; this probably won't work)
    for nf in not_found:
        b.trust(nf)

