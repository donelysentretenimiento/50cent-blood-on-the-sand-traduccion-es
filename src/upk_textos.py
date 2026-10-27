"""Lectura y reescritura de textos visibles en objetos Kismet de paquetes BotS (UE3, Xbox 360, big-endian).
Recorre las propiedades etiquetadas de forma estricta y recursiva (StructProperty anidadas) y, al cambiar una cadena,
recalcula el tamano de TODAS las estructuras contenedoras. Los demas bytes se copian tal cual."""
import hashlib, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upk_objetos as U, upk_editar as E

TARGETS = {  # clase -> propiedades StrProperty que son texto visible para el jugador
    'C1SeqVar_Tutorial': {'Header', 'MainText'},
    'C1SeqVar_Objective': {'Description', 'DetailedDescription', 'Name'},
    'C1SeqAct_DisplayDrivingMessage': {'Message', 'MessageTitle'},
}
NATIVE = {'Vector', 'Rotator', 'Color', 'LinearColor', 'Guid', 'Vector2D', 'Quat', 'Matrix', 'Plane', 'Box', 'TwoVectors', 'Vector4', 'Cylinder', 'Sphere'}
i32 = lambda d, p: struct.unpack_from('>i', d, p)[0]


def read_fstring(d, q):
    n = i32(d, q)
    if n > 0: return d[q + 4:q + 3 + n].decode('latin-1'), 4 + n
    if n < 0: return d[q + 4:q + 4 - 2 * n - 2].decode('utf-16-be'), 4 - 2 * n
    return '', 4


def tkey(cls, prop, text): return f'{cls}|{prop}|{hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]}'


def walk(d, names, p, end, cls, mapping, found):
    """Reescribe las propiedades en [p, end). Devuelve (bytes_nuevos, posicion_final). Lanza ValueError si la estructura no es valida."""
    out = bytearray()
    while True:
        if p + 8 > end: raise ValueError('fin sin None')
        ni = i32(d, p)
        if not 0 <= ni < len(names): raise ValueError('nombre invalido')
        nm = names[ni]
        if nm == 'None': out += d[p:p + 8]; return bytes(out), p + 8
        ti = i32(d, p + 8)
        if not 0 <= ti < len(names): raise ValueError('tipo invalido')
        tp = names[ti]; sz = i32(d, p + 16); q = p + 24; head = d[p:p + 24]
        if tp in ('StructProperty', 'ByteProperty'): head += d[q:q + 8]; q += 8
        if tp == 'BoolProperty': out += d[p:q + 1]; p = q + 1; continue
        if sz < 0 or q + sz > end: raise ValueError('tamano invalido')
        val = d[q:q + sz]
        if tp == 'StrProperty' and nm in TARGETS.get(cls, ()):
            text, n = read_fstring(d, q)
            if n != sz: raise ValueError('FString con tamano inesperado')
            found.append((cls, nm, text))
            if mapping is not None and tkey(cls, nm, text) in mapping: val = E.encode_fstring(mapping[tkey(cls, nm, text)])
        elif tp == 'StructProperty' and names[i32(d, q - 8)] not in NATIVE:
            try:
                sub = []; nested, e2 = walk(d, names, q, q + sz, cls, mapping, sub)
                if e2 == q + sz: val = nested; found.extend(sub)
            except ValueError: pass  # estructura opaca: se copia tal cual
        out += head[:16] + struct.pack('>i', len(val)) + head[20:] + val
        p = q + sz


def rewrite_object(d, names, e, cls, mapping=None):
    """-> (serial_nuevo, textos_encontrados). Con mapping=None solo lee (devuelve el serial original)."""
    found = []; off, size = e['off'], e['size']
    body, pend = walk(d, names, off + 4, off + size, cls, mapping, found)
    return d[off:off + 4] + body + d[pend:off + size], found


def export_positions(img):
    """Posicion del par (serial size, serial offset) de cada export, calculada una sola vez."""
    o = 12 + 4 + struct.unpack_from('>i', img, 12)[0] + 4
    _, _, ec, eo, _, _, _ = struct.unpack_from('>7i', img, o)
    pos, p = [], eo
    for _ in range(ec):
        pos.append(p + 32); p += 40
        p += 4 + i32(img, p) * 12 + 4
        p += 4 + i32(img, p) * 4 + 16 + 4
    return pos


def collect(d):
    """[(idx_export, clase, propiedad, texto)] de todos los textos visibles de un paquete (imagen logica)."""
    names, imports, exports = U.parse(d); res = []
    for k, e in enumerate(exports):
        cn = U.ref(e['cls'], imports, exports)
        if cn in TARGETS:
            _, found = rewrite_object(d, names, e, cn)
            res += [(k, c, p, t) for c, p, t in found]
    return res


def translate_image(d, mapping):
    """Aplica mapping {tkey: texto_es} reubicando al final cada objeto cambiado. -> (imagen_nueva, objetos_cambiados, textos_cambiados)."""
    names, imports, exports = U.parse(d); pos = export_positions(d)
    img = bytearray(d); changed = texts = 0
    for k, e in enumerate(exports):
        cn = U.ref(e['cls'], imports, exports)
        if cn not in TARGETS: continue
        new, found = rewrite_object(d, names, e, cn, mapping)
        if new == d[e['off']:e['off'] + e['size']]: continue
        struct.pack_into('>ii', img, pos[k], len(new), len(img)); img += new
        changed += 1; texts += sum(1 for c, p, t in found if tkey(c, p, t) in mapping)
    return bytes(img), changed, texts
