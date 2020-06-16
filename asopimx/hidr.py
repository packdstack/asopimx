#!/usr/bin/python3

import hid
import traceback

hid_max_pkt_size = 64

if __name__ == '__main__':
    import argparse
    import sys
    import binascii
    

    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--descriptor', help='Print Descriptor', action='store_true')
    args = parser.parse_args()

    d_path = ''
    device = None
    devices = hid.enumerate()
    print(devices)
    if not d_path: # no hid device specified
        if not devices:
            print('No devices to read.')
            sys.exit()
        elif d_path and d_path not in [d['path'] for d in devices]:
            print('Requested device not found.')
            sys.exit()
        else:
            print('Available devices:')
            for d in devices:
                print('\t%s' % d['path'].decode('utf-8'))
                for k in sorted(d.keys()):
                    h = k.replace('_', ' ').capitalize()
                    v = d[k].decode('utf-8') if isinstance(d[k], bytes) else d[k]
                    print('\t\t%s: %s' % (h, v))
            device = devices[0]
            d_path = device['path'].decode('utf-8')

        print('Reading: %s' % d_path)
        d = hid.device()
        d.open(device['vendor_id'], device['product_id'])
        if args.descriptor:
            pass # TODO
        while True:
            # TODO: set max packet size based on descriptor
            try:
                data = bytes(d.read(hid_max_pkt_size))
                dout = binascii.hexlify(data).upper()
                dout = b' '.join(dout[i:i+2] for i in range(0, len(dout), 2)).strip()
                #dout = ' '.join("{:02x}".format(c) for c in dout)
                print(dout.decode('utf-8'), end='\r')
            except OSError as e:
                print('%s: %s' % (type(e).__name__, e))
                sys.exit()
            except IOError as e:
                print('%s: %s' % (type(e).__name__, e))
                sys.exit()
            except Exception as e:
                # TODO: do something useful
                print(traceback.format_exc())
                sys.exit()
