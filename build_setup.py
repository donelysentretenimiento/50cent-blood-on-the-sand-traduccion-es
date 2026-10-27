"""Genera setup/Setup_Traduccion_ES_Donelys.exe (un solo archivo, sin Python ni dependencias) a partir de la distribucion
parche/Skullburglar_Traduccion_ES_by_Donelys (carpeta src/). Requiere: pip install pyinstaller pywebview pycryptodome lzallright pillow"""
import os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); D = HERE
PKG = os.path.join(D, 'src')
OUT = os.path.join(D, 'dist'); WORK = os.path.join(D, 'dist', '_build')
NAME = 'Setup_Traduccion_ES_Donelys'


def icono(path):
    from PIL import Image, ImageDraw, ImageFont
    S = 512; im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for y in range(S):  # degradado fuego -> sangre
        t = y / S; c = (int(255 - 60 * t), int(122 - 90 * t), int(61 - 40 * t), 255)
        d.line([(0, y), (S, y)], fill=c)
    mask = Image.new('L', (S, S), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=110, fill=255)
    im.putalpha(mask)
    d = ImageDraw.Draw(im); d.rounded_rectangle([6, 6, S - 7, S - 7], radius=104, outline=(255, 255, 255, 120), width=6)
    try: f = ImageFont.truetype('bahnschrift.ttf', 330)
    except OSError: f = ImageFont.load_default()
    w = d.textlength('D', font=f); d.text(((S - w) / 2, 70), 'D', font=f, fill=(255, 255, 255, 245))
    im.save(path, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])


def main():
    if not os.path.isdir(PKG): sys.exit('Falta la carpeta src/')
    shutil.rmtree(WORK, ignore_errors=True); os.makedirs(OUT, exist_ok=True)
    ico = os.path.join(WORK, 'icono.ico'); os.makedirs(WORK, exist_ok=True); icono(ico)
    sep = os.pathsep
    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--windowed', '--name', NAME, '--icon', ico,
           '--distpath', OUT, '--workpath', os.path.join(WORK, 'w'), '--specpath', WORK, '--paths', PKG,
           '--add-data', f'{os.path.join(PKG, "gui")}{sep}gui']
    for f in ('traducciones_es.json', 'traducciones_paquetes.json', 'paquetes_originales.json'): cmd += ['--add-data', f'{os.path.join(PKG, f)}{sep}.']
    for m in ('coalesced', 'xex_hashpatch', 'upk_core', 'upk_objetos', 'upk_editar', 'upk_textos', 'iso_xdvdfs', 'parcheador_iso', 'aplicar_traduccion', 'Crypto.Cipher.AES', 'lzallright'):
        cmd += ['--hidden-import', m]
    cmd.append(os.path.join(PKG, 'setup_gui.py'))
    subprocess.check_call(cmd)
    shutil.rmtree(WORK, ignore_errors=True)
    exe = os.path.join(OUT, NAME + '.exe'); print(exe, os.path.getsize(exe) // 2**20, 'MB')


if __name__ == '__main__': main()
