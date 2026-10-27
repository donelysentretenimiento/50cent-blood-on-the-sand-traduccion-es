"""Reconstruccion de paquetes BotS (UE3 v538, Xbox 360, LZO) a partir de una imagen logica editada.
Solo reescribe los chunks que cambian (el resto se copia tal cual); actualiza la tabla de chunks de la cabecera y conserva el
relleno final. Para cambiar el tamano de un objeto se REUBICA al final de la imagen (no se desplaza nada mas) y solo se
actualiza su entrada en la tabla de exports."""
import os, struct, sys
pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upk_core as u
import upk_objetos as U
from lzallright import LZOCompressor

BLOCK = 131072
ALIGN = 4096


def compress_chunk(blob, lzo):
    blocks = [(lzo.compress(blob[i:i + BLOCK]), min(BLOCK, len(blob) - i)) for i in range(0, len(blob), BLOCK)]
    head = struct.pack('>IIii', u.PACKAGE_TAG, BLOCK, sum(len(c) for c, _ in blocks), len(blob))
    return head + b''.join(struct.pack('>ii', len(c), n) for c, n in blocks) + b''.join(c for c, _ in blocks)


def rebuild(raw, new_img, force=False, pad_to=None):
    """raw: paquete original; new_img: imagen logica nueva (misma longitud o mas larga: el exceso va al ultimo chunk)."""
    h = u.parse_header(raw); chunks = h['chunks']; n = len(chunks)
    assert chunks == sorted(chunks) and all(chunks[i][2] + chunks[i][3] == chunks[i + 1][2] for i in range(n - 1)), 'chunks no contiguos'
    first_c = chunks[0][2]; last_end = chunks[-1][2] + chunks[-1][3]
    orig = u.decompress_package(raw); extra = len(new_img) - len(orig)
    assert extra >= 0 and new_img[:chunks[0][0]] == orig[:chunks[0][0]], 'cabecera logica alterada'
    lzo = LZOCompressor(); body, table, coff, stats = [], [], first_c, {'recomprimidos': 0, 'copiados': 0}
    for k, (uoff, usz, c_off, csz) in enumerate(chunks):
        nusz = usz + (extra if k == n - 1 else 0)
        blob = new_img[uoff:uoff + nusz]
        if not force and blob == orig[uoff:uoff + usz]:
            data = raw[c_off:c_off + csz]; stats['copiados'] += 1
        else:
            data = compress_chunk(bytes(blob), lzo); stats['recomprimidos'] += 1
        body.append(data); table.append((uoff, nusz, coff, len(data))); coff += len(data)
    summary = bytearray(raw[:first_c]); tpos = h['after_chunks'] - 16 * n
    for k, e in enumerate(table): struct.pack_into('>iiii', summary, tpos + 16 * k, *e)
    out = bytes(summary) + b''.join(body)
    pad = raw[last_end:]
    if pad and not any(pad) and len(raw) % ALIGN == 0: out += bytes(-len(out) % ALIGN)  # mantiene el alineado a 4 KB
    else: out += pad
    if pad_to and len(out) <= pad_to: out += bytes(pad_to - len(out))  # mismo tamano de archivo que el original (el TOC lo registra)
    return out, stats


def fstring_positions(b):
    """[(offset_de_la_longitud, texto)] de FStrings ASCII dentro de un bloque de datos de objeto."""
    out, i = [], b.find(b'\x00\x00')
    while 0 <= i <= len(b) - 6:
        n = struct.unpack_from('>I', b, i)[0]
        if 2 <= n <= 2000 and i + 4 + n <= len(b) and b[i + 4 + n - 1] == 0 and all(32 <= c < 127 or c in (10, 13, 9) for c in b[i + 4: i + 4 + n - 1]):
            out.append((i, b[i + 4: i + 4 + n - 1].decode('latin-1')))
        i = b.find(b'\x00\x00', i + 1)
    return out


def replace_fstrings(serial, repl):
    """repl: {texto_original: texto_nuevo}. Reescribe la FString y el campo Size de su etiqueta de propiedad (8 bytes antes:
    Size int32 + ArrayIndex int32). Devuelve los nuevos bytes del objeto."""
    out = bytearray(serial)
    for pos, txt in sorted(fstring_positions(bytes(serial)), reverse=True):
        if txt not in repl: continue
        old_n = 4 + len(txt) + 1
        assert struct.unpack_from('>i', out, pos - 8)[0] == old_n, f'etiqueta de propiedad inesperada para {txt!r}'
        arr_idx = struct.unpack_from('>i', out, pos - 4)[0]
        out[pos - 8:pos + old_n] = struct.pack('>ii', 4 + len(encode_fstring(repl[txt])) - 4, arr_idx) + encode_fstring(repl[txt])
    return bytes(out)


def encode_fstring(s):
    """FString UE3: ASCII -> int32 n + bytes + NUL; con caracteres no ASCII -> UTF-16BE con longitud negativa (n unidades incl. NUL)."""
    if all(ord(c) < 256 for c in s): b = s.encode('latin-1') + b'\0'; return struct.pack('>i', len(b)) + b  # ANSI 8 bits (como el juego, tambien con acentos)
    b = (s + '\0').encode('utf-16-be'); return struct.pack('>i', -(len(b) // 2)) + b


def export_entry_pos(img, export_index):
    """Posicion (en la imagen) del campo serial size/offset de un export."""
    d = img; o = 12
    o += 4 + struct.unpack_from('>i', d, o)[0] + 4
    _, _, ec, eo, _, _, _ = struct.unpack_from('>7i', d, o)
    p = eo
    for k in range(ec):
        if k == export_index: return p + 32
        p += 40
        p += 4 + struct.unpack_from('>i', d, p)[0] * 12 + 4
        p += 4 + struct.unpack_from('>i', d, p)[0] * 4 + 16 + 4
    raise IndexError(export_index)
