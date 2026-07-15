@echo off
cd /d "%~dp0"
python tools\daily_operation_check.py >> .tmp\status_diario.log 2>&1
