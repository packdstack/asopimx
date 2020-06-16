#!/usr/bin/python3

# NOTE: Joycon communication is inherently asynchronous
# NOTE: asyncio (and its ilk) unfortunately add some startup latency

import hid
import base64
from collections import namedtuple
import struct
from argparse import Namespace
import time
import sched
import logging

from asopimx.tools import phexlify

_logger = logging.getLogger(__name__ if __name__ != '__main__' else __file__)

class Device(Namespace):
    pass

class JCD:
    reports = {
            0x21: {
                'Report': namedtuple(
                    'Report',
                    'rid t blci bset1 xy zr rumble ack scrid scrdata'
                ),
                'format': struct.Struct('BBB3s3s3sBBB34s'),
            },
            0x30: {
                'Report': namedtuple(
                    'Report',
                    'rid t blci bset xy zr rumble saxis'
                ),
                'format': struct.Struct('BBB3s3s3sB36s'),
            },
            0x31: {
                'Report': namedtuple(
                    'Report',
                    'rid t blci bset xy zr rumble saxis nfcd'
                ),
                'format': struct.Struct('BBB3s3s3sB36s313s'),
            },
    }
    State = Namespace
    rumblen = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40] 
    # bl: 8=full, 6=medium, 4=low, 2=critical, 0=empty. LSB=Charging
    neutral = State(bl=8,ci=3,bset=b'\x00\x00\x00',x=128,y=128,z=128,r=128,rumble=rumblen,saxis=0,nfcd=0)

    class MiniCycle:
        c1i = 0x0
        c2i = 0x0
        f1 = 0x0
        mx1 = 0x0
        f2 = 0x0
        mx2 = 0x0

    def ps(self, res):
        ''' convenience fn '''
        if isinstance(res, self.State):
            #' ack scrid scrdata nfcr saxis nfcd'
            s = res
            return 'recv: %s' % ((s.bl,s.ci,s.bset,s.x,s.y,s.z,s.r),) #,s.rumble
        if type(res).__name__ == 'Report':
            return 'recv: %s' % res
        return 'recv: %s' % phexlify(bytes(res))

    def print(self, res, end='\n'):
        ''' convenience fn '''
        print(self.ps(res), end=end)

class JCDP(JCD):
    def __init__(self, dev):
        self.scheduler = sched.scheduler()
        self.devinfo = dev
        self.dev = self.devinfo.dev
        self.devfd = open(self.devinfo.path, 'rb')
        self.dev.set_nonblocking(True)
        self.gpn = 0
        self.gpn_max = 0xF
        self.read_max = 0x400
        self.lstate = self.State(**self.neutral.__dict__)
        self.lplstate = 0
        self.lplstate_confirmed = False
        self.devfd.flush() # attempt to flush device buffer

        self.init()
        super(JCDP, self).__init__()

    def init(self):
        print('enable vibration')
        self.vibrate(True)
        #print('enable IMU data (6-axis sensor)')
        #self.imu(True)
        print("disable IMU data (6-axis sensor; we're not using it)")
        self.imu(False)
        print('switching to full reports')
        self.send(0x1, 0x3, [0x30])
        #print('read device s/n (not necessary)')
        #self.read_spi(0x6002, 0xE)

    def claimed(self, devinfo):
        if devinfo.path == self.devinfo.path:
            return True

    def imu(self, on=True):
        return self.send(0x1, 0x40, [0x01 if on else 0x00])

    def vibrate(self, on=True):
        return self.send(0x1, 0x48, [0x01 if on else 0x00])

    def read_spi(self, offset, size):
        high, low = divmod(offset, 0x100)
        subargs = [low, high, size]
        print(subargs)
        return self.send(0x1, 0x10, subargs)


    def inc_gpn(self):
        if self.gpn == self.gpn_max:
            self.gpn = 0
        else:
            self.gpn += 1

    def send(self, cmd, scmd=None, scdata=None, rumble=None):
        if rumble is None:
            rumble = self.rumblen
        if scmd is None:
            scmd = 0x0
        if scdata is None:
            scdata = []
        request = [cmd,self.gpn] + rumble + [scmd] + scdata
        #request += [0x0 for _ in range(len(request), 0x40)]
        self.dev.write(request)
        self.inc_gpn()

    def handshake(self):
        ''' only necessary if connected via usb/serial (?)'''
        cmds = [
            'A1 A2 A3 A4 19 01 03 07 00 A5 02 01 7E 00 00 00',
            'A1 A2 A3 A4 19 01 03 07 00 A5 02 01 7E 00 00 00',
            'A1 A2 A3 A4 19 01 03 07 00 A5 02 01 7E 00 00 00',
            '19 01 03 07 00 91 01 00 00 00 00 24',
            '19 01 03 0F 00 91 20 08 00 00 BD B1 C0 C6 2D 00 00 00 00 00',
            '19 01 03 07 00 91 11 00 00 00 00 0E',
            '19 01 03 07 00 91 10 00 00 00 00 3D',
            '19 01 03 0B 00 91 12 04 00 00 12 A6 0F 00 00 00',
            '19 01 03 08 00 92 00 01 00 00 69 2D 1F',
        ]
        for cmd in cmds:
            print('send %s' % cmd)
            c = base64.b16decode(cmd.replace(' ', ''))
            self.dev.write(c)
            res = False
            limit = 5
            while not res and limit > 0:
                limit -= 1
                try:
                    res = self.dev.read(64, 15)
                except IOError:
                    pass
            print('recv %s' % res)

    def poll(self):
        ''' serial poll (?) '''
        cmd = '19 01 03 08 00 92 00 01 00 00 69 2D 1F'
        #print('send %s' % cmd)
        c = base64.b16decode(cmd.replace(' ', ''))
        self.dev.write(c)
        res = self.dev.read(64, 15)
        #print('recv %s' % res)
        return res

    def request_state(self):
        ''' request a state report '''
        report = self.send(0x01, 0x00)

    def observe(self):
        # self.devfd.flush() # attempt to flush device buffer
        while True:
            self.scheduler.run(blocking=False)
            r = self.read() #64 
            #r = self.read(64)
            if not r:
                #print('nothing to read %s (%s)' % (self.devinfo.product_string, self.devinfo.serial_number))
                return None
            rtype = r[0]
            rformatting = self.reports.get(rtype)
            if rtype == 0x3f:
                self.init() # wrong report format; reinitialize
            if rformatting and rtype in [0x30,0x31]:
                self.update_state(r)
                if self.lstate.bl < 6 and self.lplstate != 0x01:
                    self.plights(0, 0x01)
                elif not self.lplstate_confirmed:
                    self.plights(self.lplstate)
                return self.lstate
            elif rtype == 0x21:
                rformatting = self.reports.get(rtype)
                #print(len(r))
                report = rformatting['Report'](*rformatting['format'].unpack(bytes(r)))
                if report.scrid == 0x31:
                    #print(report.scrdata)
                    plstate = report.scrdata[0]
                    if self.lplstate == plstate:
                        self.lplstate_confirmed = True
                elif report.scrid == 0x30: # plights ack/nack
                    # MSB == 1; ack, MSB == nack
                    ack = report.ack >> 7
                    if not ack:
                        print("plights %s'd" % 'ack' if ack else 'nack')
                else:
                    print(
                        'unsupported scmd report: %s (%s)' % (
                            phexlify(bytes([report.scrid])), report.scrid
                    ))
            else:
                print('unsupported: %s' % rtype)
                print(phexlify(bytes(r)))
        

    def update_state(self, report):
        # TODO: handle state management and such in a separate thread;
        #   this should simply return the controller's current state from that thread
        if not report:
            return self.lstate # this is th ebest you're going to get
        rtype = report[0]
        rformatting = self.reports.get(rtype)
        if rformatting and rtype in [0x30,0x31]:
            # TODO: we may receive someone else's report...
            report = bytes(report)
            report = rformatting['Report'](*rformatting['format'].unpack(report))
            stv = vars(self.lstate)
            stv.update({(k,v) for k,v in report._asdict().items() if k in stv.keys()})
            s = report
            x = s.xy[0] | ((s.xy[1] & 0xf) << 8)
            y = (s.xy[1] >> 4) | (s.xy[2] << 4)
            z = s.zr[0] | ((s.zr[1] & 0xf) << 8)
            r = (s.zr[1] >> 4) | (s.zr[2] << 4)
            # TODO: check these
            bl = s.blci >> 4
            ci = s.blci << 4 >> 4
            stv.update({'x':x,'y':y,'z':z,'r':r, 'bl': bl, 'ci': ci})
        return self.lstate

    def async_poll(self):
        if self.polling:
            self.request_state()
            self.loop.call_later(.01667, self.async_poll) # .02 = 50hz, .01667 ~ 60hz, .1 = 10hz

    def info(self):
        return self.send(0x01,0x02)

    def plights(self, on=None, flash=None):
        # this is designed such that one can pass a single, full plight state,
        #    or in a human-firendly, split state format
        ## NOTE: trail effect can't be set; not supported
        if on is None and flash is None:
            # get lights
            return self.send(0x01,0x30)
        else:
            if on is None:
                on = 0
            if flash is None:
                flash = 0
            data = flash << 4
            data += on
        #data = 0x80 | 0x40 | 0x2 | 0x1
        #data = 0x20 | 0x10 | 0x8 | 0x4
        self.lplstate = data
        self.lplstate_confirmed = False
        r = self.send(0x01, 0x30, [self.lplstate])
        r = self.send(0x01, 0x31, [self.lplstate])
        return r

    def hlight(self, mcydur=0xF, intensity=0x7, cycles=1, mcycles=None):
        ''' home light, mcycles = list of up to 15 MiniCycles '''
        data = []
        self.send(0x01, 0x38, data)

    def rumble(self, timing=0xFF, freq=0.0):
        # NOTE: there's a limted set of valid variable ranges
        #    (most won't get you anything)
        import math
        import sys
        if freq < 0.0:
            freq = 0.0
        elif freq > 1252.0:
            freq = 1252.0
        freqdiv = freq/10
        if freqdiv < sys.float_info.min:
            freqlog = 0
        else:
            freqlog = math.log(freqdiv, 2)
        hex_freq = round(freqlog*32)
        hf = (hex_freq-0x60)*4
        lf = hex_freq-0x40

        hf = 0x01a8 # example
        hf_amp = 0x88
        b0 = hf & 0xFF
        b1 = min(hf + ((hf >> 8) & 0xFF), 0xFF)

        lf = 0x63 # example
        lf_amp = 0x804d
        b2 = lf + ((lf_amp >> 8) & 0xFF)
        b3 = lf_amp & 0xFF

        r = [timing, b0, b1, b2, b3] # one cont
        rumble = r + r

        #print(rumble)
        self.send(0x10, rumble=rumble)
        return []

    def report_mode(self, mode=0x30):
        self.send(0x01, mode)

    def read(self, size=None, timeout=0):
        if size is None:
            size = self.read_max
        return self.dev.read(size, timeout)

    def show_battery(self):
        bl = self.lstate.bl
        print(bl)
        btmap = {8:9,6:5,4:3,2:1}
        charging = bl & 1
        pl = (btmap.get(bl, bl) - charging) << 4
        pl = pl + charging
        #print(pl)
        self.plights(pl)

class JCL(JCDP):
    products = {
        (1406,8198),
    }

class JCR(JCDP):
    products = {
        (1406,8199)
    }

class JCP(JCD):
    def __init__(self, jcr=None, jcl=None, loop=None):
        # TODO: sanity check our inputs
        if jcr:
            self.loop = jcr.loop # we all share the same loop
        else:
            self.loop = loop
        #else:
        #    raise Exception('No loop specified')
        self.jcr = jcr
        self.jcl = jcl
        self.lstate = self.State(**self.neutral.__dict__)
        self.refresh = .01667
        # sync polling times
        self.polling = True
        #if self.jcr:
        #    self.jcr.polling = False
        #if self.jcl:
        #    self.jcl.polling = False
        super(JCP, self).__init__()
        if self.loop:
            self.loop.call_later(self.refresh, self.async_fuse_state)

    def assign_device(self, device):
        if isinstance(device, JCL):
            self.jcl = device
            jcd = self.jcl
        elif isinstance(device,JCR):
            self.jcr = device
            jcd = self.jcr
        elif isinstance(device, Device):
            d = device
            dev = d.dev
            dev.set_nonblocking(True)
            key = (d.vendor_id, d.product_id)
            if key in JCR.products:
                self.jcr = JCR(d)
                jcd = self.jcr
            elif key in JCL.products:
                self.jcl = JCL(d)
                jcd = self.jcl
            else:
                raise Exception('Unsupported device')
        else:
            raise Exception('Unsupported device: %s' % device)

        import time
        jcd.observe()
        jcd.show_battery()
        jcd.scheduler.enter(3, 1, jcd.plights, argument=(0x01, 0))

    def claimed(self, dev):
        return self.jcr.claimed(dev) or self.jcl.claimed(dev)

    def async_fuse_state(self):
        self.fuse_state()
        self.loop.call_later(self.refresh, self.async_fuse_state)

    def fuse_state(self):
        # return a fused state
        if self.jcl is None or self.jcr is None:
            _logger.warn([self.jcl, self.jcr])
            return self.lstate
        ls = self.jcl.lstate
        rs = self.jcr.lstate
        # TODO: figure out how to deal with rumble & sixaxis
        def bor(lft, r):
            # NOTE: we expect l & r to be the same length;
            #    we don't cover corner cases
            l = len(lft)
            buf = []
            for i in range(0,len(r)):
                buf.append(lft[i] | r[i % l])
            return bytes(buf)
        if ls.bset and rs.bset:
            bs = bor(ls.bset, rs.bset)
        elif ls.bset:
            bs = ls.bset
        else:
            bs = rs.bset
        self.lstate.__dict__.update({
            'x':ls.x,'y':ls.y,'z':rs.z,'r':rs.r, 'bl': min(ls.bl, rs.bl),
            'bset': bs,
        })
        return self.lstate

    def plights(self, on=None, flash=None):
        if self.jcr:
            self.jcr.plights(on,flash)
        if self.jcl:
            self.jcl.plights(on,flash)

    def observe(self):
        rs = ls = None
        if self.jcr is not None:
            rs = self.jcr.observe()
        if self.jcl is not None:
            ls = self.jcl.observe()
        if rs is None and ls is None:
            return self.lstate # nothing to do
        return self.fuse_state()

class Main:
    def __init__(self, loop=None):
        self.lasts = {}
        self.count = 0
        self.refresh = .05

        if loop is None:
            pass
            #self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop
        self.found = []
        self.pmap = {}
        for cls in [JCL, JCR]:
            for p in cls.products:
                self.pmap[p] = cls

    def find_devices(self, pair=True):
        new = []
        ds = hid.enumerate()
        for d in ds:
            d = Device(**d)
            vid = d.vendor_id 
            pid = d.product_id
            key = (vid, pid)
            if key in self.pmap.keys():
                claimed = False
                for f in self.found:
                    if f.claimed(d):
                        claimed = True
                        break # already found
                if claimed:
                    continue
                print('%s Found! (%s / %s)' % (d.product_string, d.serial_number, d.path))
                dev = hid.device()
                dev.open_path(d.path)
                d.dev = dev
        
                jcd = self.pmap[key](d) # , self.loop)
                print('info')
                #jcd.print(jcd.info())
                print('lights')
                jcd.plights(0x80 | 0x40, 0x2 | 0x1)
                #jcd.plights()
                print('rumble')
                jcd.rumble()
                new.append(jcd)
        self.found.extend(new)
    
        if pair and new and len(self.found) > 1:
            try:
                jcrs = filter(lambda x: isinstance(x, JCR), self.found)
                jcls = filter(lambda x: isinstance(x, JCL), self.found)
                if jcrs and jcls:
                    print('pairing jcds!')
                    jcp = JCP(next(jcrs), next(jcls))
                    # TODO: remove the ones we just mapped
                    self.found = [jcp]
                    #self.loop.call_soon(jcp.async_poll)
            except Exception as e:
                _logger.warn(e)

    def play(self):
        if self.count % 200 == 0:
            self.find_devices()
        if not self.found:
            self.loop.call_later(.1, self.play)
            return
    
        self.count += 1
        print(self.count, end=' ')
        prints = 1
        for jcd in self.found:
            prints += 1
            try:
                jcd.plights(0x01, 0)# 0x80 | 0x40, 0x2 | 0x1)
                #r = jcd.poll_state()
                r = jcd.lstate
                #r = jcd.read(30)
                if r:
                    p = jcd.ps(r)
                else:
                    p = False
                if p:
                    self.lasts[prints] = p
                elif prints not in lasts:
                    self.lasts[prints] = ''
        
            except IOError:
                pass
            print(self.lasts[prints] or '', end=' ')
        print('', end='\r')   
        self.loop.call_later(self.refresh, self.play)
    
    def main(self):
        self.loop.call_soon(self.play)
        self.loop.run_forever()

    def run_forever(self):
        self.loop.run_forever()

if __name__ == '__main__':
    m = Main()
    m.main()
