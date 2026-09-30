$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    py -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível criar o ambiente Python.' }
}
& $projectPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível instalar as dependências.' }
& $projectPython seed.py --demo
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível preparar a demonstração.' }
Write-Host 'Abra http://127.0.0.1:8080 no navegador.'
$backupProcess = Start-Process -FilePath $projectPython -ArgumentList @('backup.py', '--watch') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PSScriptRoot 'instance\backup.log') -RedirectStandardError (Join-Path $PSScriptRoot 'instance\backup-error.log')
try {
    & $projectPython run.py
} finally {
    if (-not $backupProcess.HasExited) { Stop-Process -Id $backupProcess.Id }
}
