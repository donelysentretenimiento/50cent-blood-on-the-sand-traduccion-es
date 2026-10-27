"""Lee/parchea la tabla de SHA-1 por archivo de default.xex (XEX2, AES-CBC, compresion basic).
Uso: xex_hashpatch.py find <xex>                 -> localiza entradas 'coalesced.*'
     xex_hashpatch.py patch <xex_in> <xex_out> <nombre> <sha1_viejo_hex> <sha1_nuevo_hex>
El patch re-cifra con la misma clave; solo cambia 20 bytes del bloque (verificado antes de escribir)."""
import struct, sys
from Crypto.Cipher import AES

RETAIL = bytes.fromhex('20B185A59D28FDC340583FBB0896BF91')

def load(path):
    b = bytearray(open(path, 'rb').read())
    peoff, secoff, nopt = struct.unpack_from('>III', b, 0x8)[0], struct.unpack_from('>I', b, 0x10)[0], struct.unpack_from('>I', b, 0x14)[0]
    peoff = struct.unpack_from('>I', b, 0x8)[0]
    opts = {struct.unpack_from('>I', b, 24 + 8 * i)[0]: struct.unpack_from('>I', b, 28 + 8 * i)[0] for i in range(nopt)}
    ff = opts[0x3FF]
    size, enc, comp = struct.unpack_from('>IHH', b, ff)
    assert enc == 1 and comp == 1, (enc, comp)
    blocks = [struct.unpack_from('>II', b, ff + 8 + 8 * i) for i in range((size - 8) // 8)]
    enc_key = bytes(b[secoff + 0x150:secoff + 0x160])
    key = AES.new(RETAIL, AES.MODE_ECB).decrypt(enc_key)
    return b, peoff, blocks, key

def decrypt(b, peoff, key):
    data = bytes(b[peoff:])
    n = len(data) & ~15
    return AES.new(key, AES.MODE_CBC, bytes(16)).decrypt(data[:n]) + data[n:]

def image(plain, blocks):
    out, o = bytearray(), 0
    for dsz, zsz in blocks:
        out += plain[o:o + dsz]; o += dsz; out += bytes(zsz)
    return bytes(out), o

def find(path):
    b, peoff, blocks, key = load(path)
    plain = decrypt(b, peoff, key)
    img, used = image(plain, blocks)
    assert img[:2] == b'MZ', 'descifrado incorrecto (clave)'
    return b, peoff, blocks, key, plain, img

def main():
    cmd = sys.argv[1]
    b, peoff, blocks, key, plain, img = find(sys.argv[2])
    print('imagen', len(img), 'bytes; MZ ok; datos', sum(d for d, _ in blocks), 'usados')
    if cmd == 'find':
        import re
        for m in re.finditer(rb'(?i)coalesced\.\w+\x00', img):
            print(hex(m.start()), m.group(), img[m.end():m.end() + 20].hex())
    elif cmd == 'patch':
        name, old, new = sys.argv[4].encode() + b'\x00', bytes.fromhex(sys.argv[5]), bytes.fromhex(sys.argv[6])
        i = img.find(name + old)
        assert i >= 0 and img.count(name + old) == 1, 'entrada no unica/no encontrada'
        # offset dentro del flujo descifrado (mapear imagen -> plain)
        o_img, o_plain, pos = 0, 0, None
        t = i + len(name)
        for dsz, zsz in blocks:
            if o_img <= t < o_img + dsz:
                pos = o_plain + (t - o_img); break
            o_img += dsz + zsz; o_plain += dsz
        assert pos is not None and plain[pos:pos + 20] == old
        newplain = plain[:pos] + new + plain[pos + 20:]
        n = len(newplain) & ~15
        cipher = AES.new(key, AES.MODE_CBC, bytes(16)).encrypt(newplain[:n]) + newplain[n:]
        out = bytes(b[:peoff]) + cipher
        assert len(out) == len(b)
        open(sys.argv[3], 'wb').write(out)
        diff = sum(1 for x, y in zip(b, out) if x != y)
        print('escrito', sys.argv[3], 'bytes distintos:', diff)

if __name__ == '__main__':
    main()
