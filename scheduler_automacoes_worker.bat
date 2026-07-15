@echo off
REM ============================================================
REM  Madame do Luar - Worker continuo de automacoes
REM  Roda loop de processamento e salva log em .tmp\automation_worker.log
REM ============================================================
SET PROJETO=d:\ANTIGRAVTY PROJETOS\AGENTS\MADAME DO LUAR
SET LOGDIR=%PROJETO%\.tmp

cd /d "%PROJETO%"
echo [%DATE% %TIME%] Iniciando automation_worker >> "%LOGDIR%\automation_worker.log"
python tools\automation_worker.py >> "%LOGDIR%\automation_worker.log" 2>&1
