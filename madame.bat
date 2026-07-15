@echo off
REM ============================================================
REM  Madame do Luar — Launcher de Fluxos
REM  Use este arquivo para rodar qualquer fluxo manualmente.
REM  O agendador automatico tambem chama estes scripts.
REM ============================================================

SET PROJETO=d:\ANTIGRAVTY PROJETOS\AGENTS\MADAME DO LUAR
SET PYTHON=python

echo.
echo ========================================
echo   MADAME DO LUAR — LANCADOR DE FLUXOS
echo ========================================
echo.
echo  1. Carta do Dia
echo  2. Leitura de 3 Cartas (teste)
echo  3. Processar Retornos Automaticos
echo  4. Suite de Testes Completa
echo  5. Iniciar Sistema Web
echo  0. Sair
echo.
set /p opcao="Escolha uma opcao: "

if "%opcao%"=="1" (
    echo Iniciando fluxo Carta do Dia...
    cd /d "%PROJETO%"
    %PYTHON% tools/flow_carta_do_dia.py
    pause
)
if "%opcao%"=="2" (
    echo Iniciando fluxo Leitura 3 Cartas...
    cd /d "%PROJETO%"
    %PYTHON% tools/flow_leitura_tarot.py
    pause
)
if "%opcao%"=="3" (
    echo Processando retornos automaticos...
    cd /d "%PROJETO%"
    %PYTHON% tools/flow_retorno_24h.py
    pause
)
if "%opcao%"=="4" (
    echo Rodando suite de testes...
    cd /d "%PROJETO%"
    %PYTHON% tools/test_suite.py
    pause
)
if "%opcao%"=="5" (
    echo Iniciando sistema web...
    cd /d "%PROJETO%"
    call iniciar_sistema.bat
)
if "%opcao%"=="0" exit
