# AsopiMX
An input multiplexer for Raspberry Pi (Zero W).

Connect controllers to AsopiMX via Bluetooth/USB and multiplex their input to the host OS (via USB).

Usage Examples:
* Pair 2 Switch Joycons and multiplex them to appear as a single controller to a Windows computer.
* Attach a PS3 controller and remap input to better match a different controller's input profile.

Tested on: Rapberry Pi Zero W, Raspbian 10.

## TODO
* add OS host command support (controller lights, rumble, etc.)
* improve support for existing controller profiles (battery level notifications, etc.)
* improve support for games on Windows (without requiring any Windows driver/stack manipulation apps)
* improve documentation, deployment, and overall user experience

# Installation
Aside from the below dependencies, the machine must be configured to support USB OTG and composite USB devices.
There are a number of tutorials online, but the gist of it is:
1.  Add `modules-load=dwc2` to the kernel command prompt to load the `dwc2` module on startup.
    For Raspbian this is in `/boot/cmdline.txt` and should look something like this:

        console=serial0,115200 console=tty1 root=PARTUUID=<some-uuid> rootfstype=ext4 elevator=deadline fsck.repair=yes rootwait modules-load=dwc2

2.  Add `libcomposite` to `/etc/modules` so it loads on startup.
3.  AsopiMX will try to do it for you, but ensure `dwc2` and `libcomposite` are both loaded using `lsmod` and `modprobe`.
4.  Ensure you know which port your USB OTG port will be.  For the RPi0W, this will be the one between the HDMI and far right USB port.
    This is the port you'll be plugging into your host system.
    You can optionally use a USB dongle that uses the underside USB test points (and typically sits on the bottom), but it's not necessary.
5.  Download AsopiMX.

        git clone https://github.com/packdstack/asopimx.git
        cd asopimx

6.  Install and run, or optionally run it from the source folder.

        sudo python3 setup.py install
        sudo asopimx

    or

        sudo python3 -m asopimx.mx

    Use `-w` to keep your wireless connection up. (This can lead to degraded performance.)

        sudo python3 -m asopimx.mx -w

7.  Check `-h` or `--help` for additional options, such as listing/changing device profiles.

## Dependencies

Some specific dependencies that may not be available in most repos.

* [hidapi (hidraw)](https://github.com/trezor/cython-hidapi)

        git clone https://github.com/trezor/cython-hidapi.git
        cd cython-hidapi
        git submodule update --init
        python setup.py build --without-libusb
        sudo python setup.py install --without-libusb

* [bluew](https://github.com/nullp0tr/bluew.git)

        git clone https://github.com/nullp0tr/bluew.git
        cd bluew
        sudo python setup.py install

## Resources

* [isticktoit.net - Composite USB Gadgets on the Raspberry Pi Zero](https://github.com/girst/hardpass-sendHID)
* USB HID Descriptors (via usbhid-dump)

        grep -v : devices/ps4/usbhid-dump | xxd -r -p | ~/bin/hidrd-convert -o spec

* Bluetooth Descriptors (currently via hidraw-pure (vpelletier; GPL)

## Notes
* Registry Keys - Windows caches responses to MS OS descriptor requests:

        HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\usbflags
