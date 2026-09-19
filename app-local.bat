@echo off
REM Abre o aplicativo leadpipe so neste computador (sem URL publica).
cd /d "%~dp0"
call .venv\Scripts\activate.bat
lp.exe ui
pause
