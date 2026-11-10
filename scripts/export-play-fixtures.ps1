# Export protocol fixtures for the game client (play/).
#
# 1. export_play_sample reads two characters and some of their cards from the
#    configured database (read-only: SELECT queries only).
# 2. The contract test plays a scripted game with those cards on the in-memory
#    SQLite test database and saves every step's envelopes plus cards.json.
#
# -Synthetic skips step 1 and uses built-in placeholder cards (no database).
# See docs/PLAY_PROTOCOL.md.
param(
    [string]$OutDir = (Join-Path (Split-Path $PSScriptRoot -Parent) 'play\fixtures'),
    [string]$P1 = '3',
    [string]$P2 = '2',
    [switch]$Synthetic
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }

New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path
Get-ChildItem -LiteralPath $OutDir -Filter 'step-*.json' | Remove-Item -Confirm:$false
$sample = Join-Path $OutDir 'source\sample.json'

$previousFixture = $env:LUMEN_PLAY_FIXTURE_DIR
$previousSample = $env:LUMEN_PLAY_SAMPLE
Push-Location (Join-Path $root 'LumenGG')
try {
    if (-not $Synthetic) {
        & $python -X utf8 manage.py export_play_sample --p1 $P1 --p2 $P2 --out $sample
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $env:LUMEN_PLAY_SAMPLE = $sample
    }
    else {
        Remove-Item Env:\LUMEN_PLAY_SAMPLE -ErrorAction SilentlyContinue
    }
    $env:LUMEN_PLAY_FIXTURE_DIR = $OutDir
    & $python manage.py test `
        battlelog.test_play_protocol.PlayEnvelopeContractTests.test_scripted_game_envelopes_satisfy_the_contract `
        --settings=LumenGG.test_settings --noinput
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
    if ($null -eq $previousFixture) { Remove-Item Env:\LUMEN_PLAY_FIXTURE_DIR -ErrorAction SilentlyContinue }
    else { $env:LUMEN_PLAY_FIXTURE_DIR = $previousFixture }
    if ($null -eq $previousSample) { Remove-Item Env:\LUMEN_PLAY_SAMPLE -ErrorAction SilentlyContinue }
    else { $env:LUMEN_PLAY_SAMPLE = $previousSample }
}

if ($code -ne 0) { exit $code }
$count = (Get-ChildItem -LiteralPath $OutDir -Filter 'step-*.json').Count
Write-Output "Saved $count fixture files to $OutDir"
