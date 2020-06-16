#!/usr/bin/python3

''' rfkill (accessed via /dev/rfkill)
SEE: linux/rfkill.h
'''

from collections import namedtuple
import select
import struct


class Type:
    all = 0
    wlan = 1
    bluetooth = 2
    uwb = 3

class Op:
    add = 0
    rm = 1
    change = 2
    change_all = 3

event_format = 'IBBBB'
event_size = struct.calcsize(event_format)
Event = namedtuple('Event', ['idx', 'type', 'op', 'softblock', 'hardblock'])

class Device(Event):
    pass # methods defined further down

def rflist():
    with open('/dev/rfkill', 'rb') as f:
        controllers = []
        p = select.poll()
        p.register(f)
        while True:
           rs = p.poll()
           readable = 0
           for r in rs:
               fd, event = r
               # we're only watching one file...
               if select.POLLIN & event:
                   data = f.read(event_size)
                   evt = Device(*struct.unpack(event_format, data))
                   controllers.append(evt)
                   readable += 1
           if not readable:
               break # we've read everything
    return controllers

def switch(idx, block=None):
    cs = rflist() # find our target; we want to get the type right
    if isinstance(idx, Event):
        idx = idx.idx
    try:
        c = [i for i in cs if i.idx == idx][0]
        if block is None: # behave like a switch
            block = 0 if c.softblock else 1
        with open('/dev/rfkill', 'wb') as f:
            f.write(struct.pack(
                event_format, idx, c.type,
                Op.change, block, c.hardblock
            ))
            f.flush()
    except Exception as e:
        raise Exception('Unable to update controller: %s' % e)

def rfblock(idx):
    switch(idx, 1)

def rfunblock(idx):
    switch(idx, 0)

def toggle(idx):
    switch(idx)

class rfkill:
    @staticmethod
    def list():
        return rflist()

    @staticmethod
    def block(idx):
        return rfblock(idx)

    @staticmethod
    def unblock(idx):
        return rfunblock(idx)

    @staticmethod
    def toggle(idx):
        return switch(idx)

    @staticmethod
    def switch(idx):
        return switch(idx)

class Device(Event):
    def block(idx):
        return rfblock(idx)

    def unblock(idx):
        return rfunblock(idx)

    def toggle(idx):
        return switch(idx)

    def switch(idx):
        return switch(idx)

class wlan(rfkill):
    @staticmethod
    def list():
        cs = rflist()
        wlans = [c for c in cs if c.type == Type.wlan]
        return wlans

    @staticmethod
    def first():
        return wlan.list()[0]
    

if __name__ == '__main__':
    import time
    cs = rflist()
    wlans = [c for c in cs if c.type == Type.wlan]
    print(wlans)
    for wl in wlans:
        rfblock(wl.idx)
    print(rflist())
    time.sleep(5)
    print(rflist())
    for wl in wlans:
        rfunblock(wl.idx)

