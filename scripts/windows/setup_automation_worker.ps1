# Registra somente o worker continuo de automacoes da Madame do Luar.
# Execute como administrador no PowerShell quando quiser ativar o worker no Windows.

$PROJETO = "d:\ANTIGRAVTY PROJETOS\AGENTS\MADAME DO LUAR"
$batWorker = "$PROJETO\scripts\windows\scheduler_automacoes_worker.bat"

$acao = New-ScheduledTaskAction -Execute "cmd.exe" -Argument ("/c `"" + $batWorker + "`"")
$gatilho = New-ScheduledTaskTrigger -AtStartup
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "MadameDoLuar_AutomationWorker" `
    -Action $acao `
    -Trigger $gatilho `
    -Settings $config `
    -Description "Madame do Luar: worker continuo para automacoes, tentativas e reenvios" `
    -RunLevel Highest `
    -Force | Out-Null

Write-Host "OK: MadameDoLuar_AutomationWorker registrada."
