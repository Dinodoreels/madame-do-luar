param(
  [string]$EnvFile = ".env.production.example",
  [switch]$AllowPlaceholders,
  [string]$SmokeBaseUrl = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "== Madame do Luar: pre-deploy =="
$argsList = @("tools\predeploy_check.py", "--env-file", $EnvFile)
if ($AllowPlaceholders) { $argsList += "--allow-placeholders" }
python -B @argsList

Write-Host ""
Write-Host "== Blueprint Render =="
if (-not (Test-Path "render.yaml")) {
  throw "render.yaml nao encontrado."
}
Write-Host "render.yaml presente. Suba este repositorio no Render como Blueprint."

if ($SmokeBaseUrl) {
  Write-Host ""
  Write-Host "== Smoke test =="
  python -B tools\deploy_smoke_test.py --base-url $SmokeBaseUrl
}

Write-Host ""
Write-Host "Deploy package validado localmente."
