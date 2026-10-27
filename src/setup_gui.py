"""Setup grafico: Donelys Entretenimiento presenta la traduccion al espanol de 50 Cent: Blood on the Sand.
El usuario elige su ISO y espera: el programa comprueba la version, aplica la traduccion y crea una ISO nueva.
Todo va incluido (sin Python ni dependencias). Interfaz web local (WebView2) con diseno de cristal."""
import json, os, re, subprocess, sys, threading

if getattr(sys, 'frozen', False): HERE = sys._MEIPASS
else: HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import webview
import aplicar_traduccion as AT, iso_xdvdfs as X, parcheador_iso as P

TITLE = 'Traducción al español — 50 Cent: Blood on the Sand'
STEP = re.compile(r'^(\d)/5 ')
PKG = re.compile(r'Paquete (\d+)/(\d+)')


def gb(n): return f'{n / 2**30:.2f} GB'


class Api:
    def __init__(self): self._w = None; self.out = None; self.busy = False

    def _emit(self, **e):
        if self._w: self._w.evaluate_js('onEvento(' + json.dumps(e) + ')')

    # --- ventana ---
    def minimizar(self): self._w.minimize()
    def cerrar(self): self._w.destroy()
    def mostrar(self):
        if self.out and os.path.exists(self.out): subprocess.Popen(['explorer', '/select,', os.path.normpath(self.out)], creationflags=0x08000000)  # sin ventana de consola

    # --- seleccion ---
    def elegir_iso(self):
        r = self._w.create_file_dialog(webview.OPEN_DIALOG, file_types=('Imagen ISO (*.iso)', 'Todos los archivos (*.*)'))
        if not r: return None
        return self._inspeccionar(r[0])

    def _inspeccionar(self, iso):
        try:
            with open(iso, 'rb') as f:
                isoh = X.Iso(f); idx = X.index(isoh.entries())
                falta = [p for p in (P.XEX, P.INT) if p.lower() not in idx]
                if falta: return {'error': 'Esta imagen no es la de 50 Cent: Blood on the Sand (no encuentro ' + falta[0] + ').'}
                e = idx[P.XEX.lower()]
                if isoh.sha1(e) != AT.ORIG['xex']:
                    return {'error': 'Esta ISO no es la versión compatible (hace falta «50 Cent - Blood on the Sand (USA, Europe) (En,Fr,De)»). Otra edición no se puede traducir con este programa.'}
        except X.IsoError as ex: return {'error': str(ex)}
        except OSError as ex: return {'error': 'No puedo leer el archivo: ' + str(ex)}
        out = P.default_out(iso)
        return {'iso': iso, 'nombre': os.path.basename(iso), 'tam': gb(os.path.getsize(iso)), 'salida': out, 'espacio': self._espacio(iso, out)}

    def _espacio(self, iso, out):
        try:
            free = AT.shutil.disk_usage(os.path.dirname(os.path.abspath(out))).free
            need = os.path.getsize(iso) + (2 << 30)
            return f'Espacio libre: {gb(free)} (necesito unos {gb(need)}).' + ('' if free >= need else '  ⚠ No hay espacio suficiente: cambia el destino.')
        except OSError: return ''

    def cambiar_salida(self, iso, out):
        r = self._w.create_file_dialog(webview.SAVE_DIALOG, directory=os.path.dirname(out), save_filename=os.path.basename(out), file_types=('Imagen ISO (*.iso)',))
        if not r: return None
        p = r if isinstance(r, str) else r[0]
        if not p.lower().endswith('.iso'): p += '.iso'
        return {'salida': p, 'espacio': self._espacio(iso, p)}

    # --- trabajo ---
    def iniciar(self, iso, out):
        if self.busy: return
        self.busy = True; self.out = out
        threading.Thread(target=self._trabajo, args=(iso, out), daemon=True).start()

    def _trabajo(self, iso, out):
        api = self

        class Salida:  # captura print() del parcheador (incluye las lineas con \r)
            def write(self, s):
                for part in re.split(r'[\r\n]+', s):
                    part = part.strip()
                    if not part: continue
                    m = STEP.match(part)
                    if m: api._emit(tipo='paso', n=int(m.group(1))); api._emit(tipo='log', t=part[4:])
                    elif PKG.search(part):
                        a, b = map(int, PKG.search(part).groups()); api._emit(tipo='pct', v=0.05 + 0.10 * a / b); api._emit(tipo='log', t=f'Paquete {a} de {b}')
                    else: api._emit(tipo='log', t=part)
            def flush(self): pass

        saved = sys.stdout, sys.stderr
        sys.stdout = Salida()
        try:
            last = [0.0]
            def prog(x):
                if x - last[0] >= 0.004 or x >= 1: last[0] = x; api._emit(tipo='pct', v=x)
            res = P.patch_iso(iso, out, log=print, progress=prog)
            sys.stdout, sys.stderr = saved
            self._emit(tipo='fin', ruta=res)
        except (X.IsoError, SystemExit) as e:
            sys.stdout, sys.stderr = saved
            self._emit(tipo='error', t=str(e) if not isinstance(e, SystemExit) else str(e.code))
        except PermissionError as e:
            sys.stdout, sys.stderr = saved
            self._emit(tipo='error', t='No puedo escribir en ' + str(e.filename) + '. Cierra el programa que lo use (Xenia, el explorador…) y reintenta.')
        except Exception as e:
            sys.stdout, sys.stderr = saved
            self._emit(tipo='error', t=f'Error inesperado: {type(e).__name__}: {e}')
        finally:
            sys.stdout, sys.stderr = saved
            self.busy = False


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--iso'); ap.add_argument('--out'); ap.add_argument('--auto', action='store_true'); ap.add_argument('--vista')  # --auto: pruebas sin dialogo
    a = ap.parse_args()
    api = Api()
    html = os.path.join(HERE, 'gui', 'index.html')
    w = webview.create_window(TITLE, html, js_api=api, width=1040, height=660, resizable=False, frameless=True, easy_drag=False, background_color='#0a0706')
    api._w = w
    import threading as _t, time as _time
    listo = _t.Event(); w.events.loaded += listo.set
    def esperar(): listo.wait(20); _time.sleep(1.0)

    def precargar():
        esperar(); import time
        r = api._inspeccionar(a.iso)
        if a.out and 'salida' in r: r['salida'] = a.out
        w.evaluate_js('pintar(' + json.dumps(r) + ')')
        if a.auto and 'iso' in r: time.sleep(1.5); w.evaluate_js('iniciar()')
    def vista():  # solo para revisar el diseno de cada pantalla
        esperar()
        if a.vista == 'fin': w.evaluate_js('onEvento(' + json.dumps({'tipo': 'fin', 'ruta': P.default_out(r'I:\juegos\50 Cent - Blood on the Sand (USA, Europe) (En,Fr,De).iso')}) + ')')
        elif a.vista == 'progreso': w.evaluate_js("show('s-progreso'); paso(4); setPct(0.46); document.getElementById('p-log').textContent = 'Copiando la ISO (7.30 GB)...'")
        elif a.vista == 'error': w.evaluate_js('fallo("Esta ISO no es la versión compatible (hace falta 50 Cent - Blood on the Sand (USA, Europe) (En,Fr,De)).")')
    webview.start(precargar if a.iso else vista if a.vista else None)


if __name__ == '__main__': main()
