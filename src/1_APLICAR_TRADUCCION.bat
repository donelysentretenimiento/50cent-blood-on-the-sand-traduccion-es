@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>&1 && (set PY=python) || (set PY=py)
%PY% -c "import Crypto, lzallright" >nul 2>&1 || (echo Instalando dependencias pycryptodome y lzallright... & %PY% -m pip install --user pycryptodome lzallright)
%PY% aplicar_traduccion.py apply %*
echo.
pause
