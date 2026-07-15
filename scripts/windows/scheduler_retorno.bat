@echo off
REM ============================================================
REM  Madame do Luar — Retorno Automatico (chamado pelo Task Scheduler)
REM  Roda silenciosamente, salva log em .tmp/retorno_YYYY-MM-DD.log
REM ============================================================
SET PROJETO=d:\ANTIGRAVTY PROJETOS\AGENTS\MADAME DO LUAR
SET LOGDIR=%PROJETO%\.tmp
SET LOGFILE=%LOGDIR%\retorno_%DATE:~6,4%-%DATE:~3,2%-%DATE:~0,2%.log

cd /d "%PROJETO%"
echo [%DATE% %TIME%] Iniciando flow_retorno_24h >> "%LOGFILE%"
python tools\flow_retorno_24h.py >> "%LOGFILE%" 2>&1
echo [%DATE% %TIME%] Concluido >> "%LOGFILE%"
