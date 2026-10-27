"""Lectura y parcheo de ISOs de Xbox 360 (XDVDFS / XGD1-3) sin dependencias externas.
- Iso.entries(): lista archivos y carpetas con su sector, tamano y posicion de su entrada de directorio.
- patch_files(): sustituye el contenido de archivos de una ISO ya copiada: en su sitio si caben, y si no al final de la ISO,
  actualizando solo la entrada de directorio. El resto de la ISO queda intacto byte a byte."""
import hashlib, os, struct

SEC = 2048
BASES = (0x0, 0x2080000, 0xFD90000, 0x89D80000, 0x18300000)  # XGD1 crudo, XGD1, XGD2, XGD3, XGD3 alternativo
MAGIC = b'MICROSOFT*XBOX*MEDIA'


class IsoError(Exception): pass


class Entry:
    def __init__(self, path, sector, size, isdir, entry_off): self.path, self.sector, self.size, self.isdir, self.entry_off = path, sector, size, isdir, entry_off


class Iso:
    def __init__(self, f):
        self.f = f
        for b in BASES:
            f.seek(b + 32 * SEC)
            if f.read(20) == MAGIC: self.base = b; break
        else: raise IsoError('El archivo no parece una ISO de Xbox 360 (no encuentro MICROSOFT*XBOX*MEDIA).')
        f.seek(self.base + 32 * SEC + 20); self.root, self.root_size = struct.unpack('<II', f.read(8))

    def _walk(self, sector, size, prefix):
        self.f.seek(self.base + sector * SEC); data = self.f.read(size)
        out, stack, seen = [], [0], set()
        while stack:
            off = stack.pop()
            if off in seen or off + 14 > len(data): continue
            seen.add(off)
            left, right, sec, sz, attr, nl = struct.unpack_from('<HHIIBB', data, off)
            if left == 0xFFFF and right == 0xFFFF and sec == 0xFFFFFFFF: continue
            name = data[off + 14: off + 14 + nl].decode('latin-1')
            if left: stack.append(left * 4)
            if right: stack.append(right * 4)
            e = Entry(prefix + name, sec, sz, bool(attr & 0x10), self.base + sector * SEC + off)
            out.append(e)
            if e.isdir and sz: out += self._walk(sec, sz, e.path + '/')
        return out

    def entries(self): return self._walk(self.root, self.root_size, '')

    def read(self, e, chunk=1 << 24):
        self.f.seek(self.base + e.sector * SEC); left = e.size
        while left:
            b = self.f.read(min(left, chunk))
            if not b: raise IsoError('ISO truncada leyendo ' + e.path)
            yield b; left -= len(b)

    def read_all(self, e): return b''.join(self.read(e))

    def sha1(self, e):
        h = hashlib.sha1()
        for b in self.read(e): h.update(b)
        return h.hexdigest()


def index(entries): return {e.path.lower(): e for e in entries if not e.isdir}


def patch_files(iso_path, replacements, log=print):
    """replacements: {ruta_en_la_iso: bytes}. Modifica iso_path (una COPIA de la ISO original)."""
    with open(iso_path, 'r+b') as f:
        iso = Iso(f); idx = index(iso.entries())
        for path, data in replacements.items():
            e = idx.get(path.lower())
            if e is None: raise IsoError('La ISO no contiene ' + path)
            if (len(data) + SEC - 1) // SEC <= (e.size + SEC - 1) // SEC: sector = e.sector; donde = 'en su sitio'
            else:
                end = f.seek(0, 2); sector = (end - iso.base + SEC - 1) // SEC
                f.seek(end); f.write(b'\0' * (iso.base + sector * SEC - end))  # alinear a sector
                donde = 'al final de la ISO'
            f.seek(iso.base + sector * SEC); f.write(data)
            pad = -len(data) % SEC
            if pad: f.write(b'\0' * pad)
            f.seek(e.entry_off + 4); f.write(struct.pack('<II', sector, len(data)))
            log(f'  {path}: {len(data)} bytes ({donde})')
        f.flush(); os.fsync(f.fileno())


def verify_files(iso_path, replacements):
    """Relee la ISO resultante y comprueba que cada archivo sustituido coincide byte a byte (SHA-1)."""
    with open(iso_path, 'rb') as f:
        iso = Iso(f); idx = index(iso.entries())
        for path, data in replacements.items():
            e = idx.get(path.lower())
            if e is None or e.size != len(data) or iso.sha1(e) != hashlib.sha1(data).hexdigest(): return path
    return None
