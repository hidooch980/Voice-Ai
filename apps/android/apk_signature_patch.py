#!/usr/bin/env python3
"""Transfer public v2/v3 signatures without transferring the signing private key.

The APK must be aligned before signing, with v1/v4 signing disabled. Reconstruction
is byte-for-byte checked here, and MUST additionally pass Android apksigner verify.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct


def digest(data):
    return hashlib.sha256(data).hexdigest()


def directory(data):
    for pos in range(len(data) - 22, max(-1, len(data) - 65558), -1):
        if data[pos:pos + 4] != b'PK\x05\x06':
            continue
        if pos + 22 + struct.unpack_from('<H', data, pos + 20)[0] != len(data):
            continue
        disk, central_disk, disk_count, count, size, offset = struct.unpack_from('<HHHHII', data, pos + 4)
        if disk or central_disk or disk_count != count or count == 65535 or size == 0xffffffff or offset == 0xffffffff:
            raise ValueError('Split archives and ZIP64 are unsupported')
        if offset + size != pos or data[offset:offset + 4] != b'PK\x01\x02':
            raise ValueError('Invalid central directory')
        return pos, offset
    raise ValueError('Missing ZIP end record')


def reconstruct(unsigned, patch):
    if patch.get('format') != 1 or digest(unsigned) != patch['unsigned_sha256']:
        raise ValueError('Unsigned APK hash mismatch')
    end, offset = directory(unsigned)
    if offset != patch['central_directory_offset']:
        raise ValueError('Central directory offset mismatch')
    block = base64.b64decode(patch['signing_block'], validate=True)
    if len(block) < 32 or block[-16:] != b'APK Sig Block 42':
        raise ValueError('Invalid APK signing block')
    size = struct.unpack_from('<Q', block, len(block) - 24)[0] + 8
    padding = len(block) - size
    # apksigner may insert zero padding before its 4 KiB aligned signing block.
    if size < 32 or not 0 <= padding < 4096 or any(block[:padding]):
        raise ValueError('Invalid signing block padding')
    if struct.unpack_from('<Q', block, padding)[0] != size - 8:
        raise ValueError('Invalid signing block size')
    result = bytearray(unsigned[:offset] + block + unsigned[offset:])
    struct.pack_into('<I', result, end + len(block) + 16, offset + len(block))
    if digest(result) != patch['signed_sha256']:
        raise ValueError('Reconstructed APK hash mismatch')
    return bytes(result)


def extract(unsigned, signed):
    end, offset = directory(unsigned)
    signed_end, signed_offset = directory(signed)
    if signed_offset <= offset or unsigned[:offset] != signed[:offset]:
        raise ValueError('Signing changed ZIP entries; disable v1 signing and align first')
    patch = dict(format=1, unsigned_sha256=digest(unsigned), signed_sha256=digest(signed),
                 central_directory_offset=offset,
                 signing_block=base64.b64encode(signed[offset:signed_offset]).decode('ascii'))
    if reconstruct(unsigned, patch) != signed:
        raise ValueError('Signing changed ZIP content')
    return patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['extract', 'apply'])
    parser.add_argument('unsigned', type=Path)
    parser.add_argument('signature_or_signed', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.action == 'extract':
        args.output.write_text(json.dumps(extract(args.unsigned.read_bytes(), args.signature_or_signed.read_bytes()), indent=2) + '\n')
    else:
        args.output.write_bytes(reconstruct(args.unsigned.read_bytes(), json.loads(args.signature_or_signed.read_text())))


if __name__ == '__main__':
    main()
