@echo off
REM ============================================================
REM  Madame do Luar - Campanha diaria de carta do dia renovada
REM  Agenda email/WhatsApp para usuarios com opt-in e processa fila
REM ============================================================
SET PROJETO=d:\ANTIGRAVTY PROJETOS\AGENTS\MADAME DO LUAR
SET LOGDIR=%PROJETO%\.tmp
SET LOGFILE=%LOGDIR%\carta_do_dia_%DATE:~6,4%-%DATE:~3,2%-%DATE:~0,2%.log

cd /d "%PROJETO%"
echo [%DATE% %TIME%] Iniciando daily_card_renewal >> "%LOGFILE%"
python tools\daily_card_renewal.py --process >> "%LOGFILE%" 2>&1
echo [%DATE% %TIME%] Concluido >> "%LOGFILE%"
