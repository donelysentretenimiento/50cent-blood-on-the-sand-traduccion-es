"""Parser/escritor de Coalesced.* (UE3 Xbox 360): int32 BE n; n x [FString nombre][FString contenido].
FString: int32 BE len (incluye NUL); len<0 => UTF-16BE de -len unidades."""
import struct, sys, io, re

def _rd(b, o):
    (n,) = struct.unpack_from('>i', b, o); o += 4
    if n >= 0:
        s = b[o:o+n]; o += n
        return ('a', s[:-1] if s.endswith(b'\0') else s), o
    n = -n
    s = b[o:o+2*n]; o += 2*n
    return ('w', s[:-2].decode('utf-16-le')), o

def parse(b):
    (cnt,) = struct.unpack_from('>i', b, 0); o = 4
    out = []
    for _ in range(cnt // 2):
        (k, name), o = _rd(b, o)
        (kc, body), o = _rd(b, o)
        out.append((name, kc, body))
    assert o == len(b), (o, len(b))
    return out

def _wr(kind, v):
    if kind == 'a':
        d = v + b'\0'
        return struct.pack('>i', len(d)) + d
    d = (v + '\0').encode('utf-16-le')
    return struct.pack('>i', -(len(d)//2)) + d

def build(entries):
    o = struct.pack('>i', 2*len(entries))
    for name, kc, body in entries:
        o += _wr('a', name) + _wr(kc, body)
    return o

def _as(kind, v):
    """old/new pueden llegar como str o bytes: 'a' trabaja en bytes (latin-1), 'w' en str (UTF-16)."""
    if kind == 'a': return v.encode('latin-1') if isinstance(v, str) else v
    return v.decode('latin-1') if isinstance(v, bytes) else v

def replace_line(entries, file_suffix, section, old, new, by_key=False):
    """by_key=False: reemplaza la linea exacta `old` por `new`. by_key=True: `old` es la clave y `new` el valor;
    reemplaza la unica linea 'clave=...' de la seccion por 'clave=valor' (no hace falta conocer el texto original)."""
    replacements = []
    count = 0
    for i, (name, kind, body) in enumerate(entries):
        if not name.endswith(file_suffix):
            continue
        a = kind == 'a'
        eol, br0, br1 = (b'\r\n', b'[', b']') if a else ('\r\n', '[', ']')
        # separar solo por \r y \n (str.splitlines tambien parte por U+0085, U+2028...)
        lines = body.splitlines(keepends=True) if a else re.findall(r'[^\r\n]*(?:\r\n|\n|\r)|[^\r\n]+', body)
        wanted = br0 + (section.encode('ascii') if a else section) + br1
        o, n_ = _as(kind, old), _as(kind, new)
        current = b'' if a else ''
        for j, line in enumerate(lines):
            raw = line.rstrip(eol)
            if raw.startswith(br0) and raw.endswith(br1):
                current = raw
            elif current == wanted and (raw.startswith(o + ('=' if not a else b'=')) if by_key else raw == o):
                lines[j] = (o + ('=' if not a else b'=') + n_ if by_key else n_) + line[len(raw):]
                count += 1
        replacements.append((i, (name, kind, (b'' if a else '').join(lines))))
    if count != 1:
        raise ValueError(f'expected one matching line, found {count}')
    for i, entry in replacements:
        entries[i] = entry
    return count

if __name__ == '__main__':
    p = sys.argv[1]
    b = open(p, 'rb').read()
    e = parse(b)
    print(len(e), 'entradas;', 'roundtrip', build(e) == b)
    print(sum(1 for x in e if x[1] == 'w'), 'en UTF-16')
