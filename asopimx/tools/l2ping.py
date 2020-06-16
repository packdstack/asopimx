#!/usr/bin/python3

''' l2ping - Ping bluetooth devices via L2CAP to check their availability, etc.
Most(?) bluetooth devices support public pings.
Scapy & Bluez can probably do this, too.
'''

# TODO: handle socket/bluetooth-related exceptions (known exceptions (OSError/ConnectionResetError, etc.) shouldn't print tracebacks)

import socket
from ctypes import *
import struct
import select
from datetime import datetime
import time

# this really should be defined elsewhere
# (we really don't need all this, but might was well supply 'em to learn what's all there)
# TODO: flesh out & organize where applicable

class l2cap:
    class cmd_hdr(Structure):
        _pack_ = 1
        _fields_ = [
    	    ('code', c_uint8),
            ('ident', c_uint8),
            ('len', c_uint16),
        ]
    mtu = 672
    flush_to = 0xffff
    options = 0x01
    conninfo = 0x02
    lm = 0x03
    lm_master = 0x0001
    lm_auth = 0x0002
    lm_encrypt = 0x0004
    lm_trusted = 0x0008
    lm_reliable = 0x0010
    lm_secure = 0x0020
    command_rej = 0x01
    conn_req = 0x02
    conn_rsp = 0x03
    conf_req = 0x04
    conf_rsp = 0x05
    disconn_req = 0x06
    disconn_rsp = 0x07
    echo_req = 0x08
    echo_rsp = 0x09
    info_req = 0x0a
    info_rsp = 0x0b
    create_req = 0x0c
    create_rsp = 0x0d
    move_req = 0x0e
    move_rsp = 0x0f
    move_cfm = 0x10
    move_cfm_rsp = 0x11
    feat_flowctl = 0x00000001
    feat_retrans = 0x00000002
    feat_bidir_qos = 0x00000004
    feat_ertm = 0x00000008
    feat_streaming = 0x00000010
    feat_fcs = 0x00000020
    feat_ext_flow = 0x00000040
    feat_fixed_chan = 0x00000080
    feat_ext_window = 0x00000100
    feat_ucd = 0x00000200
    fc_l2cap = 0x02
    fc_connless = 0x04
    fc_a2mp = 0x08
    hdr_size = 4
    cmd_hdr_size = 4
    cmd_rej_size = 2
    conn_req_size = 4
    conn_rsp_size = 8
    cr_success = 0x0000
    cr_pend = 0x0001
    cr_bad_psm = 0x0002
    cr_sec_block = 0x0003
    cr_no_mem = 0x0004
    cs_no_info = 0x0000
    cs_authen_pend = 0x0001
    cs_author_pend = 0x0002
    conf_req_size = 4
    conf_rsp_size = 6
    conf_success = 0x0000
    conf_unaccept = 0x0001
    conf_reject = 0x0002
    conf_unknown = 0x0003
    conf_pending = 0x0004
    conf_efs_reject = 0x0005
    conf_opt_size = 2
    conf_mtu = 0x01
    conf_flush_to = 0x02
    conf_qos = 0x03
    conf_rfc = 0x04
    conf_fcs = 0x05
    conf_efs = 0x06
    conf_ews = 0x07
    conf_max_size = 22
    mode_basic = 0x00
    mode_retrans = 0x01
    mode_flowctl = 0x02
    mode_ertm = 0x03
    mode_streaming = 0x04
    servtype_notraffic = 0x00
    servtype_besteffort = 0x01
    servtype_guaranteed = 0x02
    disconn_req_size = 4
    disconn_rsp_size = 4
    info_req_size = 2
    info_rsp_size = 4
    it_cl_mtu = 0x0001
    it_feat_mask = 0x0002
    ir_success = 0x0000
    ir_notsupp = 0x0001
    create_req_size = 5
    create_rsp_size = 8
    move_req_size = 3
    move_rsp_size = 4
    move_cfm_size = 4
    move_cfm_rsp_size = 2

# defaults
ident = 200


def ping(args):
    # stats
    sent = 0
    recvd = 0

    socks = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_RAW, proto=socket.BTPROTO_L2CAP)
    #socks.setblocking(True) # equivalent to socks.settimeout(None)
    #socks.setblocking(False) # equivalent to socks.settimeout(0.0)

    # bind to local device
    socks.bind((args.device, 0))

    # connect to remote device
    socks.connect((args.addr, 0))

    # get local address
    addr = socks.getsockname()

    send_data = bytearray()
    for i in range(0,args.size):
        send_data.append(i % 40 + ord('A'))

    id = ident
    try:
        while args.count <= 0:
            if args.count > 0:
                args.count -= 1
            send_cmd = l2cap.cmd_hdr()
            send_cmd.ident = id
            send_cmd.len = args.size
            if args.reverse:
                send_cmd.code = l2cap.echo_rsp
            else:
                send_cmd.code = l2cap.echo_req

            sent_on = datetime.now()

            # send echo command
            msg = bytes(send_cmd) + send_data
            socks.send(msg)
            
            lost = 0
            # wait for echo
            pf = select.poll()
            pf.register(socks, select.POLLIN)
            while True:
                # POLLIN
                try:
                    pf.poll(args.timeout * 1000)
                except select.error as e:
                    print(e)
                    lost = 1
                    break

                explen = l2cap.cmd_hdr_size + args.size
                r = socks.recv(l2cap.cmd_hdr_size)

                rhdr = l2cap.cmd_hdr.from_buffer_copy(r)
                # check for our id
                if rhdr.ident != id:
                    continue

                # check type
                if not args.reverse and rhdr.code == l2cap.echo_rsp:
                    break
                if rhdr.code == l2cap.command_rej:
                    print("Peer doesn't support echo packets; but they apparently exist")
                    # close, free, exit/return
                    return
            sent += 1

            if not lost:
                recvd += 1
                recvd_on = datetime.now()
                delta = recvd_on - sent_on
            
                if args.verify:
                    # check payload len
                    if rhdr.len != args.size:
                        print('Received %s bytes, expected %s' % (rhdr.len, args.size))
                        # close, free, exit/return
                        return
                    # check payload
                    if send_data != recv_data:
                        print('Response payload different.')
                        # close, free, exit/return
                        return

                print('%s bytes from %s id %s time %s' % (rhdr.len, args.addr, id - ident, delta))
                if args.delay:
                    time.sleep(args.delay)
            else:
                print('no response from s: id %s' % (args.addr, id - ident))

            id += 1
            if id > 254:
                id = ident

    except KeyboardInterrupt:
        print() # skip keyboard entry line
        
    loss = sent if (sent - recvd)/(sent/100) else 0
    print('%s sent, %s received, %s%% loss' % (sent, recvd, loss))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser('l2ping', description='L2CAP ping - ' + __doc__)
    parser.add_argument('-i', '--device', type=str, default=socket.BDADDR_ANY)
    parser.add_argument('-s', '--size', type=int, default=44)
    parser.add_argument('-c', '--count', type=int, default=-1)
    parser.add_argument('-t', '--timeout', type=int, default=10)
    parser.add_argument('-d', '--delay', type=int, default=1)
    parser.add_argument('-f', '--flood', action='store_true', help='Flood ping')
    parser.add_argument('-r', '--reverse', action='store_true', help='Reverse ping')
    parser.add_argument('-v', '--verify', action='store_true', help='Verify req & resp payload')
    parser.add_argument('addr', help='Remote bluetooth device (MAC) address')
    args = parser.parse_args()

    if args.device and args.device != socket.BDADDR_ANY:
        # TODO: figure out what device they want to use
        try:
            args.device = int(args.device)
        except:
            if args.device.startswith('hci'):
                try:
                    args.device = int(args.device[3:])
                except:
                    pass
        if isinstance(args.device, int):
            raise Exception("device resolution not currently supported; please supply the device's local (MAC) address")
    ping(args)

