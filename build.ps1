param([switch]$SkipTests, [string]$OutputRoot)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Project .venv is missing. Create the Python 3.12 environment described in README.md first.'
}
Push-Location -LiteralPath $projectRoot
try {
    New-Item -ItemType Directory -Path 'artifacts' -Force | Out-Null
    if (-not $SkipTests) {
        $testFolder = 'artifacts\build-test-' + [guid]::NewGuid().ToString('N')
        & $projectPython -m pytest tests -q -p no:cacheprovider --basetemp $testFolder --tb=short
        if ($LASTEXITCODE -ne 0) { throw 'Automated tests failed.' }
    }
    if ($OutputRoot) { & $projectPython build_release.py --output-root $OutputRoot }
    else { & $projectPython build_release.py }
    if ($LASTEXITCODE -ne 0) { throw 'Release build failed.' }
}
finally { Pop-Location }
