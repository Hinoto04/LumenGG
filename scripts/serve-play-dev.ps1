# Isolated game server for the game client (play/).
#
# 1. export_play_bundle reads the active automatic ruleset, the active AI policy,
#    cards and a few public decks from the configured database (read-only).
#    Skipped when .temp/play-dev/bundle.json exists, unless -Refresh is given.
# 2. serve_play_dev.py loads the bundle into .temp/play-dev/play.sqlite with the
#    test settings and runs Daphne on 127.0.0.1:8874. The configured database is
#    never written to.
#
# Then run "npm run dev" in play/ and open http://127.0.0.1:5175/.
# See docs/PLAY_PROTOCOL.md.
param(
    [string]$P1 = '3',
    [string]$P2 = '2',
    [int]$Port = 8874,
    [switch]$Refresh,
    [switch]$Reset
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
$bundle = Join-Path $root '.temp\play-dev\bundle.json'

if ($Refresh -or -not (Test-Path -LiteralPath $bundle)) {
    Push-Location (Join-Path $root 'LumenGG')
    try {
        & $python manage.py export_play_bundle --p1 $P1 --p2 $P2 --out $bundle
        if ($LASTEXITCODE -ne 0) { throw 'export_play_bundle failed' }
    }
    finally {
        Pop-Location
    }
    # A new bundle needs a fresh database.
    $Reset = $true
}

$serveArgs = @((Join-Path $root 'scripts\serve_play_dev.py'), '--bundle', $bundle, '--port', $Port)
if ($Reset) { $serveArgs += '--reset' }
& $python -u @serveArgs
