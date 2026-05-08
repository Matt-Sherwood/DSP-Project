$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
$runner = Join-Path $PSScriptRoot 'run_regression_tests.py'

if (-not (Test-Path $pythonExe)) {
    throw "Python environment not found at $pythonExe"
}

Set-Location $repoRoot
& $pythonExe $runner @args
