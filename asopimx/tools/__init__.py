#!/usr/bin/python3

# NOTE: there's a ton of ways to manage bits:
#    numpy, BitVector, bitarray, butstring, numba, plain python...
#    (haven't a preference atm)

import os
import errno
import binascii
from decimal import Decimal as D
import numpy
import io
import logging

_logger = logging.getLogger(__name__)

def makedirs(name, mode=0o777, exist_ok=False):
    try:
        os.makedirs(name)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(name):
            pass
        else:
            raise

def write(data, fname):
    if isinstance(data, str):
        # perhaps we should warn them if they're using a string...
        data = data.encode()
    with open(fname, 'wb') as f:
        f.write(data)

def phexlify(data):
    ''' hexlify data into a printable, readable format '''
    dout = binascii.hexlify(data).upper()
    dout = b' '.join(dout[i:i+2] for i in range(0, len(dout), 2)).strip()
    #dout = ' '.join("{:02x}".format(c) for c in dout)
    return dout.decode('utf-8')

def hz(hzs):
    ''' hz/cycle calculator
    hzs: hz or cycle in seconds
        if hz, returns cycle in seconds, else hz
    '''
    v = 1 / hzs
    if v > 1:
        return round(v, 2)
    return v

def encode_bools(bool_lst):
    # if isinstance(bool_lst, BitVector):
    #     return bool_lst.int_val()
    #     # s = io.BytesIO()
    #     # bool_lst.write_bits_to_stream_object(s)
    #     # return s.getvalue()
    # TODO: test numpy.packbits (if bool_lst is multiple of 8)
    # numpy.packbits(bool_lst).tobytes()
    # numpy version (fast) (list size limit?)
    return numpy.sum(2**numpy.arange(len(bool_lst))*bool_lst)
    # plain python version (pretty darn fast, too)
    res = 0
    for i, bval in enumerate(bool_lst):
        if bval: res += 1 << i
    return res

def decode_bools(intval, bits):
    # return BitVector(intVal=intval, size=bits).reverse()
    # plain python
    res = []
    for bit in range(bits):
        mask = 1 << bit
        res.append((intval & mask) == mask)
    return res

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


# TODO: test!
from path import Path
class PathIO():
    ''' path-like object using object/item traversal for path traversal
    not really suitable for general usage; it's fine for ConfigFS,
    but not flexible enough for more complex file management (atm)
    '''
    def __init__(self, path):
        super(PathIO, self).__setattr__('path', path)

    def __setattr__(self, key, value):
        fpath = super(PathIO, self).__getattribute__('path')
        path = Path(fpath)
        kpath = path/key
        if isinstance(value, str):
            with kpath.open('w') as f:
                f.write(value)
        elif isinstance(value, PathIO):
            vfpath = super(PathIO, value).__getattribute__('path')
            vpath = Path(vfpath)
            try:
                vpath.symlink(kpath)
            except FileExistsError:
                kpath.unlink()
                vpath.symlink(kpath)
        elif value is None:
            kpath.makedirs()

    def __getattribute__(self, key):
        fpath = super(PathIO, self).__getattribute__('path')
        path = Path(fpath)
        kpath = path/key
        if kpath.isdir():
            return PathIO(kpath)
        elif kpath.isfile():
            return kpath.text() # kpath.bytes()
        elif not kpath.exists():
            return PathIONE(kpath)
        else:
            raise Exception('unsupported type')

    def __delattr__(self, key):
        fpath = super(PathIO, self).__getattribute__('path')
        path = Path(fpath)
        kpath = path/key
        if not kpath.exists():
            pass # warn?
        elif kpath.islink():
            kpath.unlink()
        elif kpath.isdir():
            kpath.rmdir()
        else:
            kpath.unlink()

    # item (array-like) access (for paths that require string values)

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        return setattr(self, key, value)

    def __delitem__(self, key):
        return delattr(self, key)

import os
class PathIONE(PathIO):
    ''' a non-existent path
    setting an attribute will trigger path creation
    '''
    def __setattr__(self, key, value):
        # since we've inherited PathIO, we access it's super directly
        path = object.__getattribute__(self, 'path')
        # revert to os for exist_ok
        os.makedirs(path, exist_ok=True)
        super(PathIONE, self).__setattr__(key, value)



gadget_conf_dir = '/sys/kernel/config/usb_gadget/'

class Gadget(object):
    def __init__(self, name):
        self.name = name
        self.gadget = PathIO(gadget_conf_dir)[self.name]

    def add_function(self, function, config):
        if isinstance(self.gadget.functions[function], PathIONE):
            self.gadget.functions[function] = None
        self.gadget.configs[config][function] = self.gadget.functions[function]

    def remove_function(self, function, config):
        del self.gadget.configs[config][function]

    def bind(self, udc):
        _logger.info('Binding to %s', udc)
        self.gadget.UDC = udc

    def remove_gadget(self):
        del PathIO(gadget_conf_dir)[self.name]


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=str, help='File containing encoded data')
    args = parser.parse_args()
    with open(args.file) as f:
        import codecs
        d = f.read().strip(' "\n') #.encode('utf-8')
        #print(d)
        #d = codecs.escape_decode(bytes(d, 'utf8')) #.decode('utf8'))
        #d = bytes(d, 'raw')
        d = bytes(d, 'utf8').decode('unicode_escape')
        #print(d)
        print(phexlify(bytes(d, 'utf8')))
