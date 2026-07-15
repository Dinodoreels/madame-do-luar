# ============================================================
# setup_agendamentos.ps1
# Registra as tarefas agendadas da Madame do Luar no Windows
# EXECUTE COMO ADMINISTRADOR:
#   Clique com botao direito > "Executar com PowerShell"
# ============================================================

$PROJETO = "d:\ANTIGRAVTY PROJETOS\AGENTS\MADAME DO LUAR"

Write-Host ""
Write-Host "=============================================="
Write-Host "  MADAME DO LUAR - CONFIGURANDO AGENDAMENTOS"
Write-Host "=============================================="
Write-Host ""

# ── Tarefa 1: Retorno Automatico (a cada 1 hora) ──
Write-Host "Registrando Tarefa 1: Retorno Automatico (a cada hora)..."

$batRetorno = "$PROJETO\scripts\windows\scheduler_retorno.bat"

$acao1    = New-ScheduledTaskAction -Execute "cmd.exe" -Argument ("/c `"" + $batRetorno + "`"")
$gatilho1 = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 1) -Once -At (Get-Date)
$config1  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "MadameDoLuar_RetornoAutomatico" `
    -Action $acao1 `
    -Trigger $gatilho1 `
    -Settings $config1 `
    -Description "Madame do Luar: processa retornos automaticos de hora em hora" `
    -RunLevel Highest `
    -Force | Out-Null

Write-Host "  OK: MadameDoLuar_RetornoAutomatico registrada."

# ── Tarefa 2: Status Diario as 09:00 ──
Write-Host "Registrando Tarefa 2: Status Diario (09:00 todo dia)..."

$cmdStatus = "/c cd /d `"$PROJETO`" && python tools\status.py >> .tmp\status_diario.log 2>&1"

$acao2    = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmdStatus
$gatilho2 = New-ScheduledTaskTrigger -Daily -At "09:00"
$config2  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable -RunOnlyIfNetworkAvailable

Register-ScheduledTask `
    -TaskName "MadameDoLuar_StatusDiario" `
    -Action $acao2 `
    -Trigger $gatilho2 `
    -Settings $config2 `
    -Description "Madame do Luar: salva painel de status diariamente as 09:00" `
    -RunLevel Highest `
    -Force | Out-Null

Write-Host "  OK: MadameDoLuar_StatusDiario registrada."

# ── Verificacao final ──
Write-Host ""
# Tarefa 3: Carta do Dia Renovada as 08:05
Write-Host "Registrando Tarefa 3: Carta do Dia Renovada (08:05 todo dia)..."

$batCartaDia = "$PROJETO\scripts\windows\scheduler_carta_do_dia.bat"

$acao3    = New-ScheduledTaskAction -Execute "cmd.exe" -Argument ("/c `"" + $batCartaDia + "`"")
$gatilho3 = New-ScheduledTaskTrigger -Daily -At "08:05"
$config3  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "MadameDoLuar_CartaDoDiaRenovada" `
    -Action $acao3 `
    -Trigger $gatilho3 `
    -Settings $config3 `
    -Description "Madame do Luar: avisa por email e WhatsApp quando a carta do dia e renovada" `
    -RunLevel Highest `
    -Force | Out-Null

Write-Host "  OK: MadameDoLuar_CartaDoDiaRenovada registrada."

Write-Host "Tarefas ativas no Windows:"
Get-ScheduledTask | Where-Object { $_.TaskName -like "MadameDoLuar*" } | Format-Table TaskName, State -AutoSize

Write-Host "Agendamentos configurados com sucesso!"
Write-Host ""
Read-Host "Pressione Enter para fechar"
