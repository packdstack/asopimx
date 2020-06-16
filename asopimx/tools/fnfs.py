
# functionfs compatability layer
# SEE: functionfs.h for additonal details on descriptor formats
# TODO: some of the often-used fields into their own classes
# TODO: ch9.h 470 - 660; supply expected utility functions
# TODO: Test! Test! Test!

import ctypes
from enum import IntEnum

from ioctl import IOCTL

# to save some sanity
u8 = ctypes.c_uint8
le16 = ctypes.c_uint16
le32 = ctypes.c_uint32

class USB:
    class Dir(IntEnum):
        OUT = 0   # to device
        IN = 0x80 # to host
    class Type(IntEnum):
        mask = 0x03 << 5
        standard = 0x00 << 5
        klass = 0x01 << 5
        vendor = 0x02 << 5
        reserved = 0x03 << 5
    class Recipient(IntEnum):
        mask = 0x1f
        device = 0x00
        interface = 0x01
        endpoint = 0x02
        other = 0x03
        # wireless
        port = 0x04
        rpipe = 0x05
    class Request(IntEnum):
        status = 0x00
        clear_feature = 0x01
        set_feature = 0x03
        set_address = 0x05
        get_descriptor = 0x06
        set_descriptor = 0x07
        get_configuration = 0x08
        set_configuration = 0x09
        get_interface = 0x0a
        set_interface = 0x0b
        sync_frame = 0x0c
        set_sel = 0x30
        set_isoc_delay = 0x31
        # wireless
        set_enc = 0x0d # ryption
        get_enc = 0x0e # ryption
        abort_rpipe = 0x0e
        set_handshake = 0x0f
        reset_rpipe = 0x0f
        get_handshake = 0x10
        set_connection = 0x11
        set_sec_data = 0x12 # urity
        get_sec_data = 0x13 # urity
        set_wusb_data = 0x14
        write_loopback = 0x15
        read_loopback = 0x16
        set_interface_ds = 0x17
        # power delivery
        get_partner_pdo = 20
        get_battery_status = 21
        set_pdo = 22
        get_vdm = 23
        send_vdm = 24
    class Device(IntEnum):
        powered = 0 # self; read-only
        remote_wakeup = 1 # dev can wake up host
        test = 2 # high-speed only
        battery = 2 # wireless
        b_hnp_enable = 3 # dev can switch dev/host role (Host Negotiation Protocol)
        wusb = 3 # wireless
        a_hnp_support = 4 # remote host port suports HNP
        a_hnp_alt_support = 5 # other remote host port supports HNP
        debug = 6
        # USB 3.0 spec
        u1_enable = 48
        u2_enable = 49
        ltm_enable = 50 # lightning (?)
        # power delivery
        battery_wake_mask = 40
        pd_aware_os = 41
        policy = 42
    class INTRF:
        suspend = 0
        class Suspend(IntEnum):
            lp = (1 << (8))
            rw = (1 << (9))
        class Stat:
            rw_cap = 1
            rw = 2
    class Endpoint:
        halt = 0
        number_mask = 0x0f # in bEndpointAddress
        dir_mask = 0x80
        max_adjustable = 0x80
        xfer_type_mask = 0x03
        class Xfer(IntEnum):
            ctl = 0
            isoc = 1
            bulk = 2
            int = 3
        class MaxP:
            mask = 0x07ff
            class Mult:
                shift = 11
                mask = 3 << shift
            def mult(m):
                return m & USB.Endpoint.MaxP.Mult.mask >> USB.Endpoint.MaxP.Mult.shift
        class INTR:
            type = 0x30
            periodic = 0 << 4
            notification = 1 << 4
        class Sync:
            type = 0x0c
            none = 0 << 2
            async = 1 << 2
            adaptive = 2 << 2
            sync = 3 << 2
        class Usage:
            mask = 0x30
            data = 0x00
            feedback = 0x10
            imp_fb = 0x20 # implicit feedback
        # NOTE: properly classified, these would be redundant
        def num(ep_desc): # 0 -> 15
            return ep_desc.bEndpointAddress & USB.Endpoint.number_mask
        def type(ep_desc):
            return USB.Endpoint.Xfer(ep_desc.bmAttributes & USB.Endpoint.xfer_type_mask)
        class Switch:
            mask = 0x03
            no = 0
            siwtch = 1
            scale = 2
    class Dev:
        class Stat:
            u1_enabled = 2
            u2_enable = 3
            ltm_enabled = 4
    class Port: # power delivery spec
        pr_swap = 43
        goto_min = 44
        return_power = 45
        class PD:
            accept = 46
            reject = 47
            reset_port = 48
            change = 49
            reset_cable = 50
            charging_policy = 54
    class OTG:
        srp = 1 << 0
        hnp = 1 << 1
        adp = 1 << 2
        sts_selector = 0xF000
    class Wireless:
        class Attributes(IntEnum):
            p2p_drd = 1 << 1
            beacon_mask = 3 << 2
            beacon_self = 1 << 2
            beacon_directed = 2 << 2
            beacon_none = 3 << 1
        class PhyRates(IntEnum):
            p53 = 1 << 0
            p80 = 1 << 1
            p107 = 1 << 2
            p160 = 1 << 3
            p200 = 1 << 4
            p320 = 1 << 5
            p400 = 1 << 6
            p480 = 1 << 7
    class ExtCap:
        class Attributes:
            lpm_support = 1 << 1
            besl_support = 1 << 1
            besl_basline_valid = 1 << 1
            besl_deep_valid = 1 << 1
        baseline = lambda p: (p & (0xf << 8)) >> 8
        deep = lambda p: (p & (0xf << 12)) >> 12
    class SSCap:
        class Attributes:
            ltm_support = 1 << 1
        class Speeds:
            low = 1
            full = 1 << 1
            high = 1 << 2
            gbps5 = 1 << 3
    class SSPCap:
        class Attributes:
            sl_spd_attributes = (0x1f << 0) # sublink speed
            sl_spd_ids = (0xf << 5)
        class Functionality:
            min_sl_speed_attr_id = 0xf
            min_rx_lane_count = 0xf << 8
            min_tx_lane_count = 0xf << 12
        class SublinkSpeed:
            ssid = 0xf
            lse = 0x3 << 4
            st = 0x3 << 6
            rsvd = 0x3f << 8
            lp = 0x3 << 14
            lsm = 0xff << 16
    class PDCap:
        capable = 0x06
        battery_info = 0x07
        consumer_port = 0x08
        provider_port = 0x09
        class Attributes:
            battery_charging = 1 << 1
            usb_pd = 1 << 2
            provider= 1 << 3
            consumer = 1 << 4
            charging_policy = 1 << 5
            type_c_current = 1 << 6
            pwr_ac = 1 << 8
            pwr_bat = 1 << 9
            pwr_use_v_bus = 1 << 14
        class Consumer:
            bc = 1 << 0
            pd = 1 << 1
            type_c = 1 << 2
            unkown_peak_power_time = 0xffff
        class Provider:
            bc = 1 << 0
            pd = 1 << 1
            type_c = 1 << 2
    class Handshake(ctypes.LittleEndianStructure):
        _pack_ = 1
        _fields = [
            ('bMessageNumber', u8),
            ('bStatus', u8),
            ('tTKID', u8 * 3),
            ('bReserved', u8),
            ('CDID', u8 * 16),
            ('nonce', u8 * 16),
            ('mic', u8 * 8),
        ]
    class ConnectionContext(ctypes.LittleEndianStructure):
        _pack_ = 1
        _fields = [
            ('chid', u8 * 16),
            ('cdid', u8 * 16),
            ('ck', u8 * 16),
        ]
    class Speed(IntEnum):
        unknown = 0,
        low = 1,
        full = 2,
        high = 3,
        wireless = 4,
        s = 5, # super
        splus = 6,
    class State(IntEnum):
        notattached = 0
        attached = 1
        powered = 2
        reconnecting = 3
        unauthenticated = 4
        default = 5
        address = 6
        configured = 7
        suspended = 8
    class LPM(IntEnum):
        u0 = 0
        u1 = 1
        u2 = 2
        u3 = 3

    ss_mult = lambda p: 1 + (p & 0x3)
    ssp_isoc_cmp = lambda: p & (1 << 7)
    self_power_vbus_max_draw = 100 # mA

class USB3:
    class LPM(IntEnum):
        disabled = 0
        u1_max_timeout = 0x7f
        u2_max_timeout = 0xfe
        device_initiated = 0xff
        # NOTE: these don't really belong here
        max_u1_sel_pel = 0xff
        max_u2_sel_pel = 0xffff

class SetSelReq(ctypes.LittleEndianStructure): # we may not need this
    _pack_ = 1
    _fields = [
        ('u1sel', u8),
        ('u1pel', u8),
        ('u2sel', le16),
        ('u2pel', le16),
    ]


# USB 2.0 spec
class Test(IntEnum):
    j = 1
    k = 2
    se0_nak = 3
    packet = 4
    force_en = 5


class Magic(IntEnum):
    DESCRIPTORS = 1
    STRINGS = 2
    DESCRIPTORSV2 = 3

class Flags(IntEnum):
    FS_DESC = 1
    HS_DESC = 2
    SS_DESC = 4
    MS_DESC = 8
    VIRT_ADDR = 16
    EVENTFD = 32
    ALL_CTRL_RECIP = 64
    SETUP = 128

class CountReserved(ctypes.LittleEndianStructure):
    _fields = [
        ('bCount', u8),
        ('Reserved', u8),
    ]

class Count(ctypes.Union):
    _fields_ = [
        ('b', CountReserved),
        ('wCount', le16),
    ]

class Descriptor:
    class Type(IntEnum):
        # usb 2.0 spec
        device = 0x01
        config = 0x02
        string = 0x03
        interface = 0x04
        endpoint = 0x05
        qualifier = 0x06
        other_spd_config = 0x07
        interface_power = 0x08
        otg = 0x09
        debug = 0x0a
        interf_assoc = 0x0b # interface association
        # wireless
        security = 0x0c
        key = 0x0d
        enc_type = 0x0e # ryption
        bos = 0x0f
        capability = 0x10
        wl_ep_cmp = 0x011 # wireless endpoint
        adapter = 0x21 # wire adapter
        rpipe = 0x22
        cs_radio_ctl = 0x23
        pipe_usage = 0x24
        ss_ep_cmp = 0x30
        ssp_isoc_ep_cmp = 0x21
    class Class(IntEnum):
        per_interface = 0
        audio = 1
        comm = 2
        hid = 3
        phys = 5 # ical
        image = 6 # still
        printer = 7
        storage = 8 # mass
        hub = 9
        cdc_data = 0x0a
        cscid = 0x0b # chip / smart card
        content_sec = 0x0d # urity
        video = 0x0e
        wl_controller = 0xe0 # wireless
        misc = 0x0ef
        app_spec = 0xfe
        vendor_spec = 0xff
    class Subclass:
        vendor_spec = 0x0ff
    class Header(ctypes.LittleEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('bLength', u8),
            ('bDescriptorType', u8),
        ]
    class Device(ctypes.LittleEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('bLength', u8),
            ('bDescriptorType', u8),
            ('bcdUSB', le16),
            ('bDeviceClass', u8),
            ('bDeviceSublass', u8),
            ('bDeviceProtocol', u8),
            ('bMaxPacketSize0', u8),
            ('idVendor', le16),
            ('idProduct', le16),
            ('bcdDevice', le16),
            ('iManufacturer', u8),
            ('iProduct', u8),
            ('iSerialNumber', u8),
            ('bNumConfigurations', u8),
        ]
    device_size = 18 # TODO: do we really need this?
    class Config(ctypes.LittleEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('bLength', u8),
            ('bDescriptorType', u8),
            ('wTotalLength', le16),
            ('bNumInterfaces', u8),
            ('bConfigurationValue', u8),
            ('iConfiguration', u8),
            ('bmAttributes', u8),
            ('bMaxPower', u8),
        ]
    config_size = 9
    class Attributes: # config
        one = 1 << 7 # required
        self = 1 << 6 # self-powered
        wakeup = 1 << 5 # can wakeup
        battery = 1 << 4 # battery powered
    class String(ctypes.LittleEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('bLength', u8),
            ('bDescriptorType', u8),
            ('wData', le16),
        ]
    class Interface(ctypes.LittleEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('bLength', u8),
            ('bDescriptorType', u8),
            ('bInterfaceNumber', u8),
            ('bAlternateSetting', u8),
            ('bNumEndpoints', u8),
            ('bInterfaceClass', u8),
            ('bInterfaceSubClass', u8),
            ('bInterfaceProtocol', u8),
            ('iInterface', u8),
        ]
    interface_size = 9
    class Endpoint(ctypes.LittleEndianStructure): # no audio
        _fields_ = [
            ('bLength', u8),
            ('bDescriptorType', u8),
            ('bEndpointAddress', u8),
            ('bmAttributes', u8),
            ('wMaxPacketSize', le16),
            ('bInterval', u8),
        ]
    endpoint_size = 7
    class FFS:
        class Header(ctypes.LittleEndianStructure):
            # desc head v2 (original was deprecated)
            _pack_ = 1
            _fields_ = [
                ('magic', le32),
                ('length', le32),
                ('flags', le32),
            ]
    # TODO: depending on how these are used, subclass 'em
    class OS:
        class Header(ctypes.LittleEndianStructure):
            _pack_ = 1
            _anonymous_ = [
                'count',
            ]
            _fields_ = [
                ('interface', u8),
                ('dwLength', u8),
                ('bcdVersion', u8),
                ('wIndex', u8),
                ('count', Count),
            ]
    class Ext: # ended
        class Compat(ctypes.LittleEndianStructure): # ability
            _fields_ = [
                ('bFirstInterfaceNumber', u8),
                ('Reserved1', u8),
                ('CompatibleID', u8 * 8),
                ('SubCompatibleID', u8 * 8),
                ('Reserved2', u8 * 6),
            ]
        class Prop(ctypes.LittleEndianStructure): # erties
            _pack_ = 1
            _fields_ = [
                ('dwSize', le32),
                ('dwPropertyDataType', le32),
                ('wPropertyNameLength', le16),
            ]

# conventional codes for class-specific descriptors
#   (as defined by the USB Common Class spec)
class Descriptor(Descriptor):
    class Common(IntEnum):
        # conventional codes for class-specific descriptors
        #   (as defined by the USB Common Class spec)
        device = int(USB.Type.klass) | int(Descriptor.Type.device)
        config = int(USB.Type.klass) | int(Descriptor.Type.config)
        string = int(USB.Type.klass) | int(Descriptor.Type.string)
        interface = int(USB.Type.klass) | int(Descriptor.Type.interface)
        endpoint = int(USB.Type.klass) | int(Descriptor.Type.endpoint)
    class EndpointAudio(Descriptor.Endpoint): # audio
        _fields_ = [
            ('bRefresh', u8),
            ('bSyncAddress', u8),
        ]
    endpoint_audio_size = 9
    class Companion:
        class SSPIsocEndpint(Descriptor.Header):
            # SuperSpeedPlus Isochronous
            _fields_ = [
                ('wReserved', le16),
                ('dwBytesPerInterval', le32),
            ]
        ssp_isoc_endpoint_size = 8
        class SSEndpoint(Descriptor.Header):
            # SuperSpeed
            _fields_ = [
                ('bMaxMurst', u8),
                ('bmAttributes', u8),
                ('wBytesPerInterval', le16),
            ]

            def max_streams(self):
                ms = self.bmAttibutes & 0x1f
                return 1 << ms if ms else 0
        ss_size = 6
        class WirelessEndpoint(Descriptor.Header):
            _fields_ = [
                ('bMaxMurst', u8),
                ('bMaxSequence', u8),
                ('wMaxStreamDelay', le16),
                ('wOTAPacketSize', le16),
                ('bOTAInterval', u8),
                ('bmCompAttributes', u8),
            ]

    class Qualifier(Descriptor.Header):
        _fields_ = [
            ('bcdUSB', le16),
            ('bDeviceClass', u8),
            ('bDeviceSubClass', u8),
            ('bDeviceProtocol', u8),
            ('bMaxPacketSize0', u8),
            ('NumberConfigurations', u8),
            ('bReserved', u8),
        ]
    class OTG(Descriptor.Header):
        _fields_ = [
            ('bmAttributes', u8),
        ]
    class OTG20(Descriptor.Header):
        _fields_ = [
            ('bmAttributes', u8),
            ('bcdOTG', le16),
        ]
    class Debug(Descriptor.Header):
        _fields_ = [
            ('bDebugInEndpoint', u8),
            ('bDebugOutEndpoint', le16),
        ]
    class InterfaceAssociation(Descriptor.Header):
        _fields_ = [
            ('bFirstInterface', u8),
            ('bInterfaceCount', u8),
            ('bFunctionClass', u8),
            ('bFunctionSubClass', u8),
            ('bFunctionProtocol', u8),
            ('iFunction', u8),
        ]
    class Security(Descriptor.Header):
        _fields_ = [
            ('wTotalLength', le16),
            ('bNumEncryptionTypes', u8),
        ]
    class Key(Descriptor.Header):
        _fields_ = [
            ('tTKID', u8 * 3),
            ('bReserved', u8),
            ('bKeyData', u8), # TODO: check this
        ]
    class Encryption(Descriptor.Header):
        class Type(IntEnum):
            unsecure = 0
            wired = 1
            ccm = 2
            rsa = 3
        _fields_ = [
            ('bEncryptionType', u8 * 3),
            ('bEncryptionValue', u8),
            ('bAuthKeyIndex', u8), # TODO: check this
        ]
    class BOS(Descriptor.Header):
        _fields_ = [
            ('wTotalLength', le16),
            ('bNumDeviceCaps', u8),
        ]
    bos_size = 5
    class DeviceCapHeader(Descriptor.Header): # ability
        _fields_ = [
            ('bDevCapabilityType', le16),
        ]

DeviceCapHeader = Descriptor.DeviceCapHeader
class Descriptor(Descriptor):
    device_cap_type_wl = 1
    class WirelessCap(DeviceCapHeader):
        _fields_ = [
            ('bmAttributes', u8),
            ('wPhysRates', le16),
            ('bmTFITXPowerInfo', u8),
            ('bmFFITXPowerInfo', u8),
            ('bmBandGroup', le16),
            ('bReserved', u8),
        ]
    wl_cap_size = 11
    cap_type_ext = 2
    class ExtCap(DeviceCapHeader):
        _fields_ = [
            ('bmAttributes', u8),
        ]
    ext_cap_size = 7
    class SS:
        cap_type = 3
        class Cap(DeviceCapHeader):
            _fields_ = [
                ('bmAttributes', u8),
                ('wSpeedSupported', le16),
                ('bFunctionalitySupport', u8),
                ('bU1devExitLat', u8),
                ('bW2DevExitLat', le16),
            ]
        cap_size = 10
        container_id_type = 4
        class ContainerID(DeviceCapHeader):
            _fields_ = [
                ('bReserved', u8),
                ('ContainerID', u8 * 16),
            ]
        container_id_size = 30
    class SSP:
        cap_type = 0xa
        class Cap(DeviceCapHeader):
            _fields_ = [
                ('bReserved', u8),
                ('bmAttributes', le32),
                ('wFunctionalitySupport', le16),
                ('wReserved', le16),
                ('bmSublinkSpeedAttr', le32 * 2),
            ]
    class PD:
        class Cap(DeviceCapHeader):
            _fields_ = [
                ('bReserved', u8),
                ('bmAttributes', le32),
                ('bmProviderPorts', le16),
                ('bmConsumerPorts', le16),
                ('bcdBCVersion', le16),
                ('bcdPDVersion', le16),
                ('bcdUSBTypeCVersion', le16),
            ]
        class BatteryInfo(DeviceCapHeader):
            _fields_ = [
                ('iBattery', u8),
                ('iSerial', u8),
                ('iManufacturer', u8),
                ('iBatteryId', u8),
                ('rReserved', u8),
                ('dwChargedThreshold', le32), # mWh
                ('dwWeakThreshold', le32), # mWh
                ('dwBatteryDesignCapacity', le32), # mWh
                ('dwBatteryLastFullchargeCapacity', le32), # mWh
            ]
        class ConsumerPort(DeviceCapHeader):
            _fields_ = [
                ('bReserved', u8),
                ('bmCapabilities', u8),
                ('wMinVoltage', le16), # 50mV
                ('wMaxVoltage', le16), # 50mV
                ('wReserved', le16), # u16?
                ('dwMaxOperatingPower', le32), # 10mw
                ('dwMaxPeakPower', le32), # 10mW
                ('dwMaxPeakPowerTime', le32), # 100ms
            ]
        class ProviderPort(DeviceCapHeader):
            _fields_ = [
                ('bReserved', u8),
                ('bmCapabilities', u8),
                ('bNumOfPdObjects', u8),
                ('bReserved2', u8),
                ('wPowerDataObject', le32),
            ]
    class PTM:
        cap_type = 0xb
        class Cap(DeviceCapHeader):
            pass
        cap_size = 3

class Lang(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('lang', le16),
    ]

class Strings(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('magic', le32),
        ('length', le32),
        ('str_count', le32),
        ('lang_count', le32),
    ]

class CtrlRequest(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('bRequestType', u8),
        ('bRequest', u8),
        ('wValue', le16),
        ('wIndex', le16),
        ('wLength', le16),
    ]

class Setup(ctypes.Union):
    _fields_ = [
        ('setup', CtrlRequest),
    ]

class Event(ctypes.LittleEndianStructure):
    class Type(IntEnum):
        BIND = 0
        UNBIND = 1
        ENABLE = 2
        DISABLE = 3
        SETUP = 4
        SUSPEND = 5
        RESUME = 6

    class Event(ctypes.LittleEndianStructure):
        _pack_ = 1
        _fields_ = [
            ('setup', Setup),
            ('type', u8),
            ('_pad', u8),
        ]

type = ord('g')
class FIFO:
    status = IOCTL.noop(type, 1)
    flush = IOCTL.noop(type, 2)
    clear = IOCTL.noop(type, 3) # halt
    revmap_interface = IOCTL.noop(type, 128)
    revmap_endpoint = IOCTL.noop(type, 129)
    describe_endpoint = IOCTL.noop(type, 130, Descriptor.Endpoint)


# NOW!  The good stuff!
import io
import errno
class Endpoint(io.FileIO):
    # TODO: add in/out directional restrictions (defensive coding)
    def __init__(self, *args, **kwargs):
        self._halted = False
        super(Endpoint, self).__init__(*args, **kwargs)

    def _ioctl(self, f, *args, **kwargs):
        r = fnctl.ioctl(f, *args, **kwargs)
        if r < 0:
            raise IOError(r)
        return r

    def halted(self):
        return self._halted

    def halt(self, rtype=None):
        if rtype is None:
            # we're not (supposed to be) 0
            try:
                raise NotImplementedError
            except IOError as e:
                if e.errno != errno.EBADMSG:
                    raise
            else:
                raise ValueError('Halt failed.')
        else:
            try:
                if rtype & USB.Dir.IN:
                    self.read(0)
                else:
                    self.write(b'')
            except IOError as e:
                if e.errno != errno.EL2HLT:
                    raise
            else:
                raise ValueError('Failed to halt endpoint.')
        self._halted = True

    def clear(self):
        self._ioctl(FIFO.clear)
        self._halted = False

    def status(self):
        return self._ioctl(FIFO.status)

    def flush(self):
        return self._ioctl(FIFO.flush)

    def descriptor(self):
        r = Descriptor.Endpoint()
        return self._ioctl(FIFO.describe_endpoint, r, True)

    def get_iface_no(self, iface=None):
        try:
            if iface is None:
                return self._ioctl(FIFO.revmap_interface)
            else:
                return self._ioctl(FIFO.revmap_interface, iface)
        except IOError as e:
            if e.errno == errno.EDOM:
                return
            raise

class Interface:
    def __init__(self, iface, endpoints):
        self.iface = iface
        self.endpoint = endpoints
        super(Interface, self).__init__()

    

class FnFS:
    _closed = False
    _interfaces = {}

    def build_descriptors(self):
        # TODO: support other speeds
        descs = []
        flags = self.flags
        clists = []
        dlists = []
        kwargs = {}
        for iface in self._interfaces:
            descs.append(iface.iface)
            for ep in iface.endpoints:
                desc.append(ep)
        lsts = [
            (descs, Flag.HS_DESC, 'hs')
            (self._os, Flag.MS_DESC, 'os')
        ]
        for dlist, flag, pre in lsts:
            if dlist:
                flags |= flag   
                dmap = OrderedDict()
                for i, d in enumerate(dlist):
                    dmap['desc_%s' % i] = d
                cname = prefix + '_count'
                dname = prefix + '_desc'
                clists.append((cname, le32))
                dtype = type(
                    't_' + dname,
                    (ctypes.LittleEndianStructure,),
                    {   '_pack_': 1,
                        '_fields_': [
                            (x, type(y)) for x, y in dmap.items()
                ]})
                dlists.append((dname, dtype))
                kwargs[cname] = len(dmap)
                kwargs[dname] = dtype(**dmap)
        # TODO: sanity-check flags
        cls = type(
            'Descs_0x%02x' % flags,
            (Descriptor.FFS.Header,),
            { '_fields_': clists + dlists }
        )
        return cls(
            magic=Magic.DESCRIPTORSV2,
            length=ctypes.sizeof(cls),
            flags=flags, **kwargs
        )

    def build_strings():
        lst = []
        kwargs = {}
        try:
            count = len(next(iter(self._langs.values())))
        except:
            count = 0
        else:
            for lang, strings in self._langs.items():
                if len(strings) != count:
                    raise ValueError('Uneven strings count! (%s)' % lang)
                sid = 's_%04x' % lang
                bstrings = b'\x00'.join(x.encode('utf8') for x in strings) + b'\x00'
                ftype = type(
                    'String',
                    (Lang,),
                    { '_fields_':[
                        ('strings', ctypes.c_char * len(bstrings)),
                ]})
                lst.append((sid, ftype))
                kwargs[sid] = ftype(lang=lang,strings=bstrings)
        cls = type(
            'Strings',
            (Strings,),
            { '_fields_': lst }
        )
        return cls(
            magic=Magic.STRINGS,
            length=ctypes.sizeof(cls),
            str_count=count,
            lang_count=len(self._langs),
            **kwargs,
        )

    def serialize(self, s):
        return (ctypes.c_char * ctypes.sizeof(s)).from_address(ctypes.addressof(s))

    def __init__(self, path, interfaces, os=None, langs=None, ctl_all=False, setup_early=False):
        ''' create an fs function
        path: path to dir containing ep0
        interfaces: list of Interfaces
        os: os descriptors list
        langs: langs list ex: {0x0409: ['Product']}
        ctl_all: handle all ctl operations (default pending)
        setup_early: receive control messages before configuration begins
        '''
        self._path = path
        self._interfaces = interfaces
        self._os = os if os is not None else []
        self._langs = langs if lans is not None else []
        self.e0 = Endpoint(os.path.join(path, 'ep0'), 'r+')
        self.flags = 0
        if ctl_all:
            self.flags |= Flags.ALL_CTRL_RECIP
        if setup_early:
            self.flags |= Flags.SETUP 
        descriptors = self.build_descriptors()    
        self.e0.write(self.serialize(descriptors))
        strings = self.build_strings()
        self.e0.write(self.serialize(strings))
        # TODO: populate endpoints and put them to work!
