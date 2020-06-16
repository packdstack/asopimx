# AsopiMX
An input multiplexer for Raspberry Pi (Zero W).

Connect controllers to AsopiMX via Bluetooth/USB and multiplex their input to the host OS (via USB).

Usage Examples:
* Pair 2 Switch Joycons and multiplex them to appear as a single controller to a Windows computer.
* Attach a PS3 controller and remap input to better match a different controller's input profile.

## TODO
* add OS host command support (controller lights, rumble, etc.)
* improve support for existing controller profiles (battery level notifications, etc.)
* improve support for games on Windows (without requiring any Windows driver/stack manipulation apps)
* improve documentation, deployment, and overall user experience

## Resources

* [isticktoit.net - Composite USB Gadgets on the Raspberry Pi Zero](https://github.com/girst/hardpass-sendHID)
* USB HID Descriptors (via usbhid-dump)

        grep -v : devices/ps4/usbhid-dump | xxd -r -p | ~/bin/hidrd-convert -o spec

* Bluetooth Descriptors (currently via hidraw-pure (vpelletier; GPL)
* cython-hdapi (trezor): could ony get hidraw backend working (required for Bluetooth support) in python3;
    requires manual compilation (doesn't support multiple backends at runtime and insists on using libusb)
* bluew (nullp0tr): awesome python bluez accessor; requires python3

## Notes
* Registry Keys - Windows caches responses to MS OS descriptor requests:

        HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\usbflags
