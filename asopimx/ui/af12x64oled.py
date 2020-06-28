#!/usr/bin/python3

''' UI for the Adafruit 128x64 OLED Bonnet (for rpi)
NOTE: For better performance, tweak I2C core to run @ 1Mhz:
Add the following to /boot/config.txt:
    dtparam=i2c_baudrate=1000000
'''

import RPi.GPIO as gpio
import time
import enum
import sys
import traceback
import logging

from busio import SPI
import Adafruit_SSD1306

from PIL import Image, ImageDraw, ImageFont

import asopimx.tools.rfkill as rfkill
from asopimx.scheduler import Scheduler

_logger = logging.getLogger(__name__ if __name__ != '__main__' else __file__)

class Pins(enum.IntEnum):
    l = 27
    r = 23
    c = 4
    u = 17
    d = 22

    a = 5
    b = 6

gpio.setmode(gpio.BCM)
for p in Pins:
    gpio.setup(p.value, gpio.IN, pull_up_down=gpio.PUD_UP)

# reset pin
rst = None # not required

class AsopiUI:
    fonts_dir =  '/usr/share/fonts/truetype/freefont/'
    class Color:
        w = 'white'
        b = 'black'
    def __init__(self):
        # setup display
        self.disp = Adafruit_SSD1306.SSD1306_128_64(rst=rst)
        
        self.disp.begin()
        self.clear()
        
        self.width, self.height = self.disp.width, self.disp.height # 128, 64
        self.image = Image.new('1', (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)
        self.font('FreeMono.ttf')
        self.wifi_toggled = False
        self.refresh_rate = 1
        self.scheduler = Scheduler()
        self.screen = None

    def font(self, font, size=16):
        # using freemono:
        # fsize = 24 # 9x2.5
        # fsize = 16 # 12.5x4
        # fsize = 14 # 16x4.5
        # fsize = 12 # 18x5, but not very readable
        # fsize = 8 # unreadable
        self.fsize=size
        self.font = ImageFont.truetype(self.fonts_dir + font, self.fsize)
        self.twidth = 12 # TODO: assign this based on size
        return self.font

    def clear(self):
        self.disp.clear()
        self.disp.display()

    def clear_image(self):
        # another way to clear the screen
        self.draw.rectangle((0,0,self.width,self.height), outline=0,fill=0)
        # self.display()

    def display(self):
        self.disp.image(self.image)
        self.disp.display()

    def text(self, x=0, y=0, text=None, color=None, font=None):
        ''' draw text (only white and black is supported) '''
        self.draw.text(
            (x,y), text if text else '',
            color if color else self.Color.w,
            font=font if font else self.font
        )

    def test(self):
        fsize = self.fsize
        self.text(0,0,  '123456789012345678')
        self.text(0,fsize, 'ABCDEFGHIJ')
        self.text(0,fsize*2, 'abcdefghij')
        self.text(0,fsize*3, 'abcdefghij')
        self.text(0,fsize*4, 'abcdefghij')
        self.display()

    def display_status(self):
        self.clear_image()
        banner = 'AsoPiMX'.ljust(self.twidth-1)
        if self.wifi_enabled(): # wifi enabled
            # banner[-1] = 'W' # stupid immutable string  :)
            banner += 'W'
        else:
            banner += ' '
        self.text(0,0, banner)
        self.display()

    def check_input(self):
        ''' checks input; if something changes, do something '''
        if not gpio.input(Pins.a): # button pressed
            pass
        if not gpio.input(Pins.b): # button pressed
            if not self.wifi_toggled:
                self.toggle_wifi()
                self.wifi_toggled = True
        else:
            if self.wifi_toggled:
                self.wifi_toggled = False

    def wifi_status(self):
        for c in rfkill.rflist():
            if c.type == rfkill.Type.wlan:
                return c
    
    def wifi_enabled(self):
        status = self.wifi_status()
        return not status.softblock
        return True if status.softblock == 0 else False

    def toggle_wifi(self):
        rfkill.toggle(self.wifi_status())

    def refresh(self):
        self.check_input()
        self.display_status()
        if self.scheduler:
            self.scheduler.enter(self.refresh_rate, 1, self.refresh)

    def start(self):
        self.screen = 'status'
        self.refresh()

    def listen(self):
        try:
            self.screen = 'status'
            self.display_status()
            while True:
                # TODO: only call display_status() when something's changed
                self.check_input()
                self.display_status()
                # restricts excessive refresh rate & pin read bouncing
                time.sleep(self.refresh_rate) # .01 takes up too much cpu time
        except Exception as e:
            print(traceback.format_exc())
        finally: # clear display
            self.clear()

    def __enter__(self):
        return self

    def __exit__(self, etype, val, tb):
        self.clear()

if __name__ == '__main__':
    with AsopiUI() as a:
        a.listen()
