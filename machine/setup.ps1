# Run from PowerShell. All arguments are forwarded to the shared Python installer.
$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot 'bootstrap.py'
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $installer --yes @args
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    & python3 $installer --yes @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $installer --yes @args
} else {
    throw 'Python 3.9 or newer is required.'
}
exit $LASTEXITCODE
