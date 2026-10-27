"""Skullburglar - Traduccion espanola by Donelys: parcheador de ISO de Xbox 360.
Uso: parcheador_iso.py <ISO_original> [<ISO_salida>]
Lee tu ISO, extrae SOLO los archivos que cambia la traduccion (Coalesced.INT, default.xex y los paquetes con textos),
verifica por SHA-1 que son los de la version compatible, aplica la traduccion y escribe una ISO NUEVA (copia de la tuya con
esos archivos sustituidos). La ISO original no se modifica. Para jugar en Xenia o en una consola desbloqueada."""
import os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import aplicar_traduccion as AT, iso_xdvdfs as X

XEX, INT = 'default.xex', 'C1Game/Localization/Coalesced.INT'
PKG_DIR = 'C1Game/CookedXenon/'


def fmt_gb(n): return f'{n / 2**30:.2f} GB'


def default_out(iso):
    b, e = os.path.splitext(iso)
    return b + ' (Traducido al español by Donelys Entretenimiento)' + (e or '.iso')


def copy_with_progress(src, dst, progress=None):
    total = os.path.getsize(src); done = 0
    with open(src, 'rb') as a, open(dst, 'wb') as b:
        while True:
            c = a.read(1 << 24)
            if not c: break
            b.write(c); done += len(c)
            if progress: progress(done / total)


def patch_iso(iso, out=None, log=print, progress=None):
    """progress(fraccion 0..1) opcional. Lanza X.IsoError / SystemExit con mensajes claros."""
    iso = os.path.abspath(iso); out = os.path.abspath(out or default_out(iso))
    if not os.path.isfile(iso): raise X.IsoError('No existe la ISO: ' + iso)
    if os.path.normcase(iso) == os.path.normcase(out): raise X.IsoError('La ISO de salida debe ser distinta de la original.')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    need = os.path.getsize(iso) + (2 << 30)
    free = shutil.disk_usage(os.path.dirname(out)).free
    if free < need: raise X.IsoError(f'Falta espacio en el disco de destino: necesito unos {fmt_gb(need)} y hay {fmt_gb(free)}.')
    tr = AT.load_translations()
    tmp = tempfile.mkdtemp(prefix='skull_es_')
    try:
        game = os.path.join(tmp, 'game')
        log('1/5 Leyendo la ISO y comprobando que es la version compatible...')
        wanted = {XEX: 'xex', INT: 'int'}
        wanted.update({PKG_DIR + n: 'pkg:' + n for n in AT.PKGS})
        with open(iso, 'rb') as f:
            isoh = X.Iso(f); idx = X.index(isoh.entries())
            missing = [p for p in wanted if p.lower() not in idx]
            if missing: raise X.IsoError(f'Esta ISO no es la compatible (faltan {len(missing)} archivos, p. ej. {missing[0]}). Hace falta 50 Cent: Blood on the Sand (USA, Europe) (En,Fr,De).')
            for i, (p, k) in enumerate(wanted.items(), 1):
                e = idx[p.lower()]; dst = AT.path(game, k); os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, 'wb') as o:
                    for b in isoh.read(e): o.write(b)
                if AT.sha1f(dst) != AT.ORIG_ALL[k]:
                    raise X.IsoError(f'{p} no coincide con la version compatible (SHA-1). Esta ISO es otra edicion o esta danada; no continuo.')
                if progress: progress(0.05 * i / len(wanted))
        log(f'    {len(wanted)} archivos verificados.')
        log('2/5 Aplicando la traduccion (tarda unos minutos)...')
        AT.apply(game, tr)
        log('3/5 Preparando los archivos nuevos...')
        repl = {p: open(AT.path(game, k), 'rb').read() for p, k in wanted.items()}
        part = out + '.parte'
        log(f'4/5 Copiando la ISO ({fmt_gb(os.path.getsize(iso))})...')
        copy_with_progress(iso, part, (lambda x: progress(0.15 + 0.7 * x)) if progress else None)
        log('5/5 Sustituyendo archivos en la copia y verificando...')
        X.patch_files(part, repl, log)
        bad = X.verify_files(part, repl)
        if bad: raise X.IsoError('Verificacion fallida en ' + bad + '; no se genera la ISO.')
        os.replace(part, out)
        if progress: progress(1.0)
        log('\nListo. ISO traducida: ' + out)
        log('La ISO original no se ha modificado.')
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if os.path.exists(out + '.parte'):
            try: os.remove(out + '.parte')
            except OSError: pass


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'): sys.exit(__doc__)
    try: patch_iso(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    except X.IsoError as e: sys.exit('ERROR: ' + str(e))
    except ImportError as e: sys.exit(f'Falta una dependencia ({e}). Instala:  python -m pip install --user pycryptodome lzallright')


if __name__ == '__main__': main()
