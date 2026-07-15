@echo off
REM ============================================================
REM  Madame do Luar - Iniciar sistema web
REM  Sobe a API FastAPI e abre o app no navegador.
REM ============================================================

cd /d "%~dp0"

echo.
echo ========================================
echo   MADAME DO LUAR - SISTEMA WEB
echo ========================================
echo.
echo  Iniciando backend em http://localhost:8000
echo  Mantenha esta janela aberta enquanto usa o sistema.
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"
python api.py

echo.
echo O servidor foi encerrado.
pause
