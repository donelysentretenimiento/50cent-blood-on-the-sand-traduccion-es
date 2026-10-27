"""Lectura/descompresion de paquetes cooked UE3 de BotS (Xbox 360, v538, chunks LZO, big-endian).
El formato de chunks y la logica de descompresion siguen la documentacion de tools/upk_decompress.py de
https://github.com/nlwstein/skullburglar (BSD 3-Clause, (c) 2026 the Skullburglar contributors); esta es una reimplementacion
propia con la misma interfaz. Aviso BSD-3: se conserva el aviso de copyright y la renuncia de garantias del proyecto original."""
import struct

from lzallright import LZOCompressor

PACKAGE_TAG = 0x9E2A83C1
COMPRESS_LZO = 2


class _R:
    def __init__(self, data, off=0): self.d, self.o = data, off
    def u32(self): v = struct.unpack_from('>I', self.d, self.o)[0]; self.o += 4; return v
    def i32(self): v = struct.unpack_from('>i', self.d, self.o)[0]; self.o += 4; return v
    def fstring(self): n = self.i32(); self.o += n if n >= 0 else -n * 2


def parse_header(data):
    """-> dict(cflags_off, cflags, chunks=[(uoff, usz, coff, csz)], after_chunks)"""
    r = _R(data)
    if r.u32() != PACKAGE_TAG: raise ValueError('no es un paquete UE3 (etiqueta incorrecta)')
    r.u32(); r.i32(); r.fstring(); r.u32()     # version, tamano de cabecera, carpeta, flags
    r.o += 7 * 4 + 16                           # contadores/offsets de nombres, exports, imports, depends + guid
    gens = r.i32(); r.o += gens * 12
    r.i32(); r.i32()                            # build del motor, version del cooker
    cflags_off = r.o; cflags = r.u32(); n = r.i32()
    chunks = [tuple(r.i32() for _ in range(4)) for _ in range(n)]
    return dict(cflags_off=cflags_off, cflags=cflags, chunks=chunks, after_chunks=r.o)


def decompress_chunk(data, off, lzo):
    r = _R(data, off)
    if r.u32() != PACKAGE_TAG: raise ValueError(f'etiqueta de chunk incorrecta en {off:#x}')
    r.u32(); r.i32(); total = r.i32()
    blocks, got = [], 0
    while got < total:
        csz, usz = r.i32(), r.i32(); blocks.append((csz, usz)); got += usz
    out = bytearray()
    for csz, usz in blocks:
        out += lzo.decompress(data[r.o:r.o + csz], output_size_hint=usz); r.o += csz
    if len(out) != total: raise ValueError(f'chunk en {off:#x}: {len(out)} bytes, se esperaban {total}')
    return bytes(out)


def decompress_package(data):
    """Imagen logica completa (la cabecera se copia tal cual, con su tabla de chunks ya obsoleta)."""
    h = parse_header(data)
    if not h['chunks']: return data
    if h['cflags'] != COMPRESS_LZO: raise ValueError(f'compresion no soportada: {h["cflags"]}')
    lzo = LZOCompressor()
    first, end = min(c[0] for c in h['chunks']), max(c[0] + c[1] for c in h['chunks'])
    out = bytearray(end); out[:first] = data[:first]
    for uoff, usz, coff, _ in h['chunks']:
        blob = decompress_chunk(data, coff, lzo)
        if len(blob) != usz: raise ValueError(f'chunk @{coff:#x}: tamano {len(blob)} != {usz}')
        out[uoff:uoff + usz] = blob
    return bytes(out)
