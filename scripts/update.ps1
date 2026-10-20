$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = if ($env:CBO_PYTHON) { $env:CBO_PYTHON } else { 'python' }
& $taskPython (Join-Path $taskRoot 'scripts/manage.py') update @args
exit $LASTEXITCODE
