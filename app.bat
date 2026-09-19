@echo off
REM Abre o aplicativo leadpipe (painel local + URL publica para o celular).
REM Dois cliques aqui. Para fechar: Ctrl+C nesta janela.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
lp.exe ui --public
pause
