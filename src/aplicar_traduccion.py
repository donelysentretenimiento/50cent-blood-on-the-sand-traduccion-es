"""Skullburglar - Traduccion espanola by Donelys: aplica / comprueba / restaura.
Uso: aplicar_traduccion.py {apply|status|restore} [--game CARPETA] [--tr traducciones.json]
Modifica solo: Coalesced.INT, default.xex y los paquetes .xxx con textos de tutorial/objetivos/conduccion.
Copias verificadas por SHA-1 en <juego>\\_backup_es. Partidas guardadas, configuracion y la ISO no se tocan.
No contiene archivos originales del juego: todo se reconstruye en local a partir de los del usuario."""
import time, argparse, glob, hashlib, json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.path.isdir(os.path.join(HERE, '..', 'paquetes')): sys.path.insert(0, os.path.join(HERE, '..', 'paquetes'))  # entorno de desarrollo
import coalesced

ORIG = {'int': '323e79463207fb810f651688541f88ee9243b82f', 'xex': 'de2569aabc937f9c6528753e2f46d624f7ff7276'}  # SHA-1 de la version compatible
BACKUP = '_backup_es'
MANIFEST = BACKUP + '/manifest.json'


def _find(*names):
    for d in (HERE, os.path.join(HERE, '..'), os.path.join(HERE, '..', 'paquetes'), os.path.join(HERE, '..', 'originales', 'paquetes')):
        for n in names:
            if os.path.isfile(os.path.join(d, n)): return os.path.join(d, n)


_pk = _find('paquetes_originales.json', 'indice_sha1.json')
PKGS = json.load(open(_pk)) if _pk else {}                       # {paquete.xxx: SHA-1 original}
ORIG_ALL = dict(ORIG, **{'pkg:' + n: h for n, h in PKGS.items()})


def sha1(b): return hashlib.sha1(b).hexdigest()
def sha1f(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()
def rel(k): return {'int': os.path.join('C1Game', 'Localization', 'Coalesced.INT'), 'xex': 'default.xex'}.get(k) or os.path.join('C1Game', 'CookedXenon', k[4:])
def path(game, k): return os.path.join(game, rel(k))
def read(game, k): return open(path(game, k), 'rb').read()
def bpath(game, k): return os.path.join(game, BACKUP, 'paquetes', k[4:]) if k.startswith('pkg:') else os.path.join(game, BACKUP, os.path.basename(rel(k)))


def write_atomic(p, data):
    tmp = p + '.tmp'
    with open(tmp, 'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)
    if sha1f(p) != sha1(data): raise IOError('Verificacion fallida tras escribir ' + p)


def find_game(arg=None):
    """Busca la carpeta del juego (la que contiene default.xex y C1Game)."""
    cands = [arg, os.environ.get('SKULLBURGLAR_GAME'), os.path.expandvars(r'%LOCALAPPDATA%\bots-recomp\game'),
             os.path.join(HERE, 'game'), os.path.join(HERE, '..', 'game'), os.path.join(os.getcwd(), 'game')]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, 'default.xex')) and os.path.isfile(path(c, 'int')): return os.path.abspath(c)
    sys.exit('No encuentro la carpeta del juego (la que contiene default.xex y C1Game).\n'
             'Indicala asi: aplicar_traduccion.py apply --game "RUTA\\game"  (por defecto: %LOCALAPPDATA%\\bots-recomp\\game)')


def manifest(game):
    mp = os.path.join(game, MANIFEST)
    return json.load(open(mp)) if os.path.exists(mp) else None


def managed(game):
    """Archivos que gestiona el parche en esta instalacion: INT, XEX y los paquetes listados que existen."""
    return ['int', 'xex'] + ['pkg:' + n for n in PKGS if os.path.isfile(path(game, 'pkg:' + n))]


def state(game):
    """('original'|'traducido'|'incompleto'|'conflicto', hashes_actuales). 'incompleto' = instalacion interrumpida (recuperable)."""
    m = manifest(game); keys = managed(game)
    if m: keys = sorted(set(keys) | {k for k in m['aplicado'] if os.path.isfile(path(game, k))})
    cur = {k: sha1f(path(game, k)) for k in keys}
    def ours(k): return ({m['aplicado'][k]} if m and k in m['aplicado'] else set()) | ({m['previo'][k]} if m and m.get('previo') and k in m['previo'] else set())
    kinds = {k: 'o' if cur[k] == ORIG_ALL.get(k) else 'a' if cur[k] in ours(k) else 'x' for k in keys}
    if 'x' in kinds.values(): return 'conflicto', cur
    if all(v == 'o' for v in kinds.values()): return 'original', cur
    if all(v == 'a' for v in kinds.values()): return 'traducido', cur
    return 'incompleto', cur


def normalize(items):
    """Acepta [seccion, clave, valor] (formato de distribucion) o [seccion, 'clave=viejo', 'clave=nuevo'] (formato de trabajo).
    Las claves nunca contienen '=', asi que se distinguen sin ambiguedad."""
    for sec, a, b in items:
        yield (sec, a, b) if '=' not in a else (sec, a.split('=', 1)[0], b.split('=', 1)[1])


def load_translations(files=None):
    base = [HERE, os.path.join(HERE, '..')]
    files = files or sorted({os.path.abspath(f) for b in base for f in glob.glob(os.path.join(b, 'traducciones_es*.json'))})
    if not files: sys.exit('No encuentro ningun archivo traducciones_es*.json junto al parcheador.')
    tr = {}
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        for k, v in d.get('lineas', d).items(): tr.setdefault(k, []).extend(v)
    return tr


def source(game, k):
    """Bytes del archivo ORIGINAL verificado: la copia de seguridad si existe; si no, el archivo actual."""
    b = bpath(game, k); p = b if os.path.exists(b) else path(game, k)
    data = open(p, 'rb').read()
    if sha1(data) != ORIG_ALL[k]: sys.exit(f'{rel(k)} no coincide con la version compatible (SHA-1); no continuo.')
    return data


def build(game, tr):
    """(int_nuevo, xex_nuevo) partiendo SIEMPRE de los originales verificados."""
    import xex_hashpatch as xh
    orig_int, orig_xex = source(game, 'int'), source(game, 'xex')
    entries = coalesced.parse(orig_int)
    for suffix, items in tr.items():
        for sec, key, val in normalize(items):
            try: coalesced.replace_line(entries, suffix.encode(), sec, key, val, by_key=True)
            except ValueError as e: sys.exit(f'Traduccion no aplicable ({suffix} [{sec}] {key}): {e}')
    new_int = coalesced.build(entries)
    with tempfile.TemporaryDirectory() as d:
        i, o = os.path.join(d, 'in.xex'), os.path.join(d, 'out.xex')
        open(i, 'wb').write(orig_xex)
        saved, sys.argv = sys.argv, ['x', 'patch', i, o, 'coalesced.int', ORIG['int'], sha1(new_int)]
        try: xh.main()
        finally: sys.argv = saved
        new_xex = open(o, 'rb').read()
    return new_int, new_xex


def build_pkg(raw, mapping):
    """Paquete traducido (mismo tamano de archivo que el original si cabe) o el original si no tiene textos que cambiar."""
    import upk_core as u, upk_textos as T, upk_editar as E
    d = u.decompress_package(raw)
    img, nobj, _ = T.translate_image(d, mapping)
    if not nobj: return raw
    out, _ = E.rebuild(raw, img, pad_to=len(raw))
    dec = u.decompress_package(out); fu = u.parse_header(raw)['chunks'][0][0]
    if len(dec) != len(img) or dec[fu:] != img[fu:]: sys.exit('Verificacion interna del paquete fallida; no continuo.')
    return out


def apply(game, tr):
    st, cur = state(game)
    if st == 'conflicto':
        sys.exit('CONFLICTO: los archivos no son los originales de la version compatible ni los de esta traduccion\n'
                 '(otro mod, otra version del juego o un archivo modificado). No toco nada.')
    keys = managed(game); pk = [k for k in keys if k.startswith('pkg:')]
    mapping = None
    if pk:
        mp = _find('traducciones_paquetes.json')
        mapping = json.load(open(mp, encoding='utf-8')) if mp else None
        if mapping is None: pk = []; keys = [k for k in keys if not k.startswith('pkg:')]
    for k in keys:  # copias de seguridad verificadas ANTES de tocar nada (por archivo: tambien en estados intermedios)
        dst = bpath(game, k)
        if os.path.exists(dst):
            if sha1f(dst) != ORIG_ALL[k]: sys.exit(f'La copia de seguridad de {rel(k)} esta danada; no continuo.')
            continue
        if sha1f(path(game, k)) != ORIG_ALL[k]: sys.exit(f'No hay copia del original de {rel(k)} y el archivo actual no es el original; no continuo.')
        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(path(game, k), dst)
        if sha1f(dst) != ORIG_ALL[k]: sys.exit('La copia de seguridad no se pudo verificar; no continuo.')
    print('Construyendo Coalesced.INT y default.xex...')
    new_int, new_xex = build(game, tr)
    new = {'int': new_int, 'xex': new_xex}; tmps, applied = {}, {'int': sha1(new_int), 'xex': sha1(new_xex)}
    for i, k in enumerate(pk, 1):                       # los paquetes se construyen a archivos temporales (sin tocar el juego)
        print(f'Paquete {i}/{len(pk)}: {k[4:]}', end='\r', flush=True)
        out = build_pkg(source(game, k), mapping); t = path(game, k) + '.es.tmp'
        with open(t, 'wb') as f: f.write(out)
        tmps[k] = t; applied[k] = sha1(out)
    if pk: print()
    m = manifest(game); man = {'original': {k: ORIG_ALL[k] for k in keys}, 'aplicado': applied}
    if m: man['previo'] = m['aplicado']
    os.makedirs(os.path.join(game, BACKUP), exist_ok=True)
    json.dump(man, open(os.path.join(game, MANIFEST), 'w'), indent=1)  # antes de escribir: permite restaurar si se interrumpe
    for k in ('int', 'xex'): write_atomic(path(game, k), new[k])
    for k, t in tmps.items():
        os.replace(t, path(game, k))
        if sha1f(path(game, k)) != applied[k]: raise IOError('Verificacion fallida tras escribir ' + rel(k))
    man.pop('previo', None); json.dump(man, open(os.path.join(game, MANIFEST), 'w'), indent=1)
    print('Traduccion aplicada:', sum(len(v) for v in tr.values()), 'lineas de Coalesced y', len(pk), 'paquetes. Ya puedes jugar.')


def restore(game):
    st, _ = state(game)
    if st == 'original': return print('Ya estan los originales; no hay nada que restaurar.')
    if st == 'conflicto': sys.exit('CONFLICTO: los archivos no coinciden con el parche; no restauro para no pisar cambios ajenos.')
    m = manifest(game); keys = [k for k in m['original'] if os.path.isfile(path(game, k))]
    for k in keys:
        if not os.path.exists(bpath(game, k)) or sha1f(bpath(game, k)) != ORIG_ALL.get(k, m['original'][k]): sys.exit(f'La copia de seguridad de {rel(k)} esta danada; no restauro.')
    for k in keys:
        t = path(game, k) + '.res.tmp'; shutil.copyfile(bpath(game, k), t); os.replace(t, path(game, k))
        if sha1f(path(game, k)) != m['original'][k]: raise IOError('Verificacion fallida al restaurar ' + rel(k))
    os.remove(os.path.join(game, MANIFEST)); print('Originales restaurados:', len(keys), 'archivos.')


def main():
    ap = argparse.ArgumentParser(description='Skullburglar - Traduccion espanola by Donelys')
    ap.add_argument('cmd', choices=['apply', 'status', 'restore'], help='apply=aplicar, status=estado, restore=restaurar originales')
    ap.add_argument('--game', default=None, help='carpeta del juego (la que contiene default.xex)')
    ap.add_argument('--tr', default=None, help='JSON de traducciones de Coalesced (por defecto, todos los traducciones_es*.json)')
    a = ap.parse_args()
    try:
        game = find_game(a.game)
        if a.cmd == 'status':
            st, cur = state(game)
            print({'original': 'ORIGINAL (sin traducir)', 'traducido': 'TRADUCIDO', 'incompleto': 'INCOMPLETO (instalacion interrumpida: ejecuta restore o apply)',
                   'conflicto': 'CONFLICTO (archivos ajenos o version no compatible)'}[st]); print('Carpeta:', game, '| archivos gestionados:', len(cur))
        elif a.cmd == 'restore': restore(game)
        else:
            tr = load_translations([a.tr] if a.tr else None)
            for intento in range(4):  # el juego recien cerrado o un antivirus pueden retener un archivo unos segundos
                try: apply(game, tr); break
                except PermissionError:
                    if intento == 3: raise
                    time.sleep(3)
    except ImportError as e:
        sys.exit(f'Falta una dependencia ({e}). Instala:  python -m pip install --user pycryptodome lzallright')
    except PermissionError as e:
        sys.exit(f'No puedo escribir en {e.filename}. Cierra el juego (y cualquier programa que use esos archivos) y vuelve a intentarlo.')


if __name__ == '__main__':
    main()
