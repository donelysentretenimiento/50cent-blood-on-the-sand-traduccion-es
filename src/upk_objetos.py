"""Utilidades de solo lectura para paquetes UE3 (BotS, Xbox 360) ya descomprimidos en memoria:
tabla de nombres, importaciones y exportaciones (clase, objeto, offset/tamano serial)."""
import os, struct, sys
pass
import upk_core as u

GAME = os.path.expandvars(r'%LOCALAPPDATA%\bots-recomp\game\C1Game\CookedXenon')


def load(pkg):
    return u.decompress_package(open(os.path.join(GAME, pkg), 'rb').read())


def parse(d):
    o = 12
    o += 4 + struct.unpack_from('>i', d, o)[0] + 4  # carpeta, flags
    nc, no, ec, eo, ic, io_, _ = struct.unpack_from('>7i', d, o)
    names, p = [], no
    for _ in range(nc):
        n = struct.unpack_from('>i', d, p)[0]
        names.append(d[p + 4: p + 3 + n].decode('latin1')); p += 4 + n + 8
    imports = []
    for k in range(ic):
        pk, cn, outer, nm = struct.unpack_from('>iiii', d, io_ + k * 28)[0:1] + struct.unpack_from('>ii', d, io_ + k * 28 + 8) + struct.unpack_from('>i', d, io_ + k * 28 + 20)
        imports.append(names[nm])
    exports, p = [], eo
    for _ in range(ec):
        cls, sup, outer, on = struct.unpack_from('>iiii', d, p)
        size, off = struct.unpack_from('>ii', d, p + 32)
        p += 24 + 8 + 8
        p += 4 + struct.unpack_from('>i', d, p)[0] * 12 + 4
        p += 4 + struct.unpack_from('>i', d, p)[0] * 4 + 16 + 4
        exports.append(dict(cls=cls, sup=sup, outer=outer, name=names[on], size=size, off=off))
    return names, imports, exports


def ref(i, imports, exports):
    return exports[i - 1]['name'] if i > 0 else imports[-i - 1] if i < 0 else 'None'


if __name__ == '__main__':
    pkg, off = sys.argv[1], int(sys.argv[2], 16)
    d = load(pkg); names, imports, exports = parse(d)
    print(f'{pkg}: {len(names)} nombres, {len(imports)} imports, {len(exports)} exports')
    for i, e in enumerate(exports):
        if e['off'] <= off < e['off'] + e['size']:
            chain, o = [], e['outer']
            while o > 0: chain.append(exports[o - 1]['name']); o = exports[o - 1]['outer']
            print('OBJETO:', e['name'], '| clase:', ref(e['cls'], imports, exports), '| dentro de:', '/'.join(reversed(chain)) or '-',
                  f'| serial off={e["off"]:#x} size={e["size"]}')
