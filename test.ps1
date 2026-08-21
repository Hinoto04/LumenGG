param(
    [ValidateSet('sqlite', 'mariadb', 'mysql')]
    [string]$Database = 'sqlite',
    [string[]]$TestLabel = @(
        'battlelog.tests',
        'battlelog.test_automatic_engine',
        'card.tests',
        'common.tests'
    )
)

$ErrorActionPreference = 'Stop'
$projectDirectory = Join-Path $PSScriptRoot 'LumenGG'
$localConfig = Join-Path $PSScriptRoot 'test.local.ps1'

if (Test-Path -LiteralPath $localConfig) {
    . $localConfig
}

$previousDatabase = $env:LUMENGG_TEST_DATABASE

try {
    $env:LUMENGG_TEST_DATABASE = $Database
    Push-Location $projectDirectory
    try {
        & python manage.py test @TestLabel --settings=LumenGG.test_settings --noinput
        $testExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($null -eq $previousDatabase) {
        Remove-Item Env:\LUMENGG_TEST_DATABASE -ErrorAction SilentlyContinue
    }
    else {
        $env:LUMENGG_TEST_DATABASE = $previousDatabase
    }
}

exit $testExitCode
