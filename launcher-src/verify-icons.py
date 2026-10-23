"""Verify ICO frames against the actual icon resources embedded in both EXEs."""
import hashlib
import json
from pathlib import Path
import struct
import sys

SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]


def u16(data, offset):
    return struct.unpack_from('<H', data, offset)[0]


def u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0]


def resources(data):
    pe = u32(data, 0x3c)
    assert data[pe:pe + 4] == b'PE\0\0', 'Invalid PE signature'
    section_count = u16(data, pe + 6)
    optional = pe + 24
    directories = optional + (96 if u16(data, optional) == 0x10b else 112)
    resource_rva = u32(data, directories + 16)
    sections = optional + u16(data, pe + 20)

    def raw(rva):
        for index in range(section_count):
            pos = sections + index * 40
            va, size, offset = u32(data, pos + 12), u32(data, pos + 16), u32(data, pos + 20)
            if va <= rva < va + max(size, u32(data, pos + 8)):
                return offset + rva - va
        raise ValueError('RVA outside PE sections')

    base = raw(resource_rva)
    result = {}

    def walk(relative, keys):
        pos = base + relative
        count = u16(data, pos + 12) + u16(data, pos + 14)
        for index in range(count):
            name, target = struct.unpack_from('<II', data, pos + 16 + index * 8)
            key = name if not name & 0x80000000 else 'named-' + str(name)
            if target & 0x80000000:
                walk(target & 0x7fffffff, keys + (key,))
            else:
                entry = base + target
                start, size = raw(u32(data, entry)), u32(data, entry + 4)
                result[keys + (key,)] = data[start:start + size]
    walk(0, ())
    return result


def check(root, name, icon_name):
    exe = (root / name).read_bytes()
    ico = (root / 'launcher-src' / icon_name).read_bytes()
    assert struct.unpack_from('<HHH', ico) == (0, 1, len(SIZES)), 'Wrong ICO header'
    table = resources(exe)
    groups = [v for k, v in table.items() if k[0] == 14]
    assert len(groups) == 1, 'Expected a single application icon group'
    group = groups[0]
    assert struct.unpack_from('<HHH', group) == (0, 1, len(SIZES)), 'Wrong embedded frame count'
    for i, size in enumerate(SIZES):
        entry = ico[6 + i * 16:6 + (i + 1) * 16]
        width, height, colors, reserved, planes, depth, length, offset = struct.unpack('<BBBBHHII', entry)
        assert (width or 256) == size and (height or 256) == size
        assert planes == 1 and depth == 32
        frame = ico[offset:offset + length]
        assert len(frame) == length
        if size == 256:
            assert frame[:8] == b'\x89PNG\r\n\x1a\n'
            assert struct.unpack_from('>II', frame, 16) == (256, 256)
            assert frame[25] == 6, 'PNG must have RGBA transparency'
        else:
            assert struct.unpack_from('<IiiHH', frame) == (40, size, size * 2, 1, 32)
            alpha = frame[43:40 + size * size * 4:4]
            assert 0 in alpha and 255 in alpha, 'Missing visible artwork or transparency'
        embedded_entry = group[6 + i * 14:6 + (i + 1) * 14]
        assert embedded_entry[:12] == entry[:12], 'Group metadata differs from source ICO'
        resource_id = u16(embedded_entry, 12)
        embedded = [v for k, v in table.items() if k[0] == 3 and k[1] == resource_id]
        assert len(embedded) == 1 and embedded[0] == frame, 'Embedded image differs from source ICO'
    return {'exe': name, 'status': 'PASS', 'sizes': SIZES, 'depth': 32,
            'embedded_frames_match_source': True,
            'sha256': hashlib.sha256(exe).hexdigest()}


if __name__ == '__main__':
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    result = {'status': 'PASS', 'icons': [check(root, 'dashboard.exe', 'frontend.ico'),
                                         check(root, 'sqlview.exe', 'backend.ico')]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
