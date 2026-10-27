@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>&1 && (set PY=python) || (set PY=py)
%PY% aplicar_traduccion.py status %*
echo.
pause
