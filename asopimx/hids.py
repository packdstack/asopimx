#!/usr/bin/python3

import argparse
import base64
import time
import logging

_logger = logging.getLogger(__name__ if __name__ != '__main__' else __file__)

class Stream():
    def __init__(self, stream, host=None, debug=False):
        ''' TODO: support streams other than filenames '''
        self.stream = stream
        self.host = host # ex: '/dev/hidg0'
        self.debug = debug

        with open(self.stream) as s:
            d = s.read()
        self.reports = []
        report = ''
        for l in d.split('\n'):
            r = l
            if ':' in r:
               continue
            if not r.strip():
                self.reports.append(report.strip())
                report = ''
                continue
            report += r

    def read(self, delay=0):
        ''' read from stream (with an optional delay (for debugging) '''
        # import binascii
        for r in self.reports:
            # NOTE: we have to open and close it for each report
            #   otherwise, it's never sent
            # TODO: find out which method is faster
            # TODO: see if there's a no-close version (\n, \r, something)
            if delay:
                time.sleep(delay)
            p = base64.b16decode(r.replace(' ', ''))
            if self.debug:
                print('%s %s' % (len(p), r), end='\r')
            #print(len(p))
            yield p
            #  alternatively, using binascii
            # f.write(binascii.a2b_hex(r.replace(' ', '')))

    def send_echo(fstream):
        ''' echo reports to file (can be ran as script to send reports) '''
        import os
        import random
        srandom = random.SystemRandom()
        f = open(fstream, 'w')
        for r in reports:
            # r = srandom.choice(reports) # random testing
            hidr = ''.join(['\\x%s' % c.lower() for c in r.split()])
            hidr = hidr.replace('\\x00', '\\0').replace('\\x0', '\\x')
            cmd  = 'echo -ne "%s" > %s' % (hidr, args.device)
            #os.system(cmd) # this doesn't work
            f.write(cmd + '\n') # this works (call with bash after generation)
        f.close()

    def send_to_host(self, delay=0):
        data = self.read(delay)
        # import binascii
        for p in data:
            # NOTE: we have to open and close it for each report
            #   otherwise, it's never sent
            # TODO: find out which method is faster
            # TODO: see if there's a no-close version (\n, \r, something)
            with open(self.host, 'wb') as f:
                f.write(p)


class ArgsParser(argparse.ArgumentParser):
    def error(self, message):
        # NOTE: this is just if we want to do something differnt; the default's fine
        self.print_usage()
        self.exit(2, '%s: error: %s\n' % (self.prog, message))

if __name__ == '__main__':
    default_hid = '/dev/hidg0'
    parser = ArgsParser(description='Sends a stream of HID reports captured by hid-dump')
    parser.add_argument('file', type=str, help='File containing HID stream')
    parser.add_argument(
        '-d', '--device', default=default_hid,
        help='Device to stream to; default: %s' % default_hid
    )
    parser.add_argument(
        '--delay', type=float, default=0,
        help='Playback delay (in seconds; ex: .01)')
    parser.add_argument('--debug', default=False, action='store_true')
    args = parser.parse_args()

    stream = Stream(args.file, args.device, args.debug)
    stream.send_to_host(args.delay)
