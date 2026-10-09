[CmdletBinding()]
param(
    [string]$CredentialsPath = 'C:\Hinoto\lumen-upload.credentials.xml',
    [ValidateRange(0, 2100000000)][int]$VersionCode = 0,
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$mobileRoot = Split-Path -Parent $PSScriptRoot
if (-not $VersionCode) {
    Push-Location -LiteralPath $mobileRoot
    try {
        $publicConfigJson = & npx.cmd expo config --type public --json
        if ($LASTEXITCODE -ne 0) { throw 'Cannot read Expo app configuration.' }
        $VersionCode = [int](($publicConfigJson -join "`n" | ConvertFrom-Json).android.versionCode)
        if ($VersionCode -lt 1) { throw 'Set android.versionCode in app.config.ts.' }
    } finally { Pop-Location }
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path (Split-Path -Parent $mobileRoot) 'artifacts'
}
$credentials = Import-Clixml -LiteralPath $CredentialsPath
if (-not (Test-Path -LiteralPath $credentials.StoreFile -PathType Leaf)) {
    throw 'Upload keystore not found.'
}
if (-not ($credentials.StorePassword -is [Security.SecureString]) -or
    -not ($credentials.KeyPassword -is [Security.SecureString])) {
    throw 'Use Windows-encrypted SecureString values in the credentials XML.'
}
$jdk = $env:JAVA_HOME
if (-not $jdk -or -not (Test-Path -LiteralPath (Join-Path $jdk 'bin\java.exe'))) {
    $jdk = 'C:\Program Files\Android\Android Studio\jbr'
}
if (-not (Test-Path -LiteralPath (Join-Path $jdk 'bin\java.exe'))) {
    throw 'Set JAVA_HOME to a JDK 21 installation.'
}

$environment = @{
    JAVA_HOME = $jdk
    ANDROID_HOME = $(if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else {
        Join-Path $env:LOCALAPPDATA 'Android\Sdk'
    })
    NODE_ENV = 'production'
    LUMEN_REQUIRE_UPLOAD_SIGNING = '1'
    LUMEN_UPLOAD_STORE_FILE = $credentials.StoreFile
    LUMEN_UPLOAD_STORE_PASSWORD = ([PSCredential]::new('upload', $credentials.StorePassword)).GetNetworkCredential().Password
    LUMEN_UPLOAD_KEY_ALIAS = $credentials.KeyAlias
    LUMEN_UPLOAD_KEY_PASSWORD = ([PSCredential]::new('upload', $credentials.KeyPassword)).GetNetworkCredential().Password
    LUMEN_VERSION_CODE = [string]$VersionCode
}
$previous = @{}
$location = Get-Location
try {
    foreach ($name in $environment.Keys) {
        $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $environment[$name], 'Process')
    }
    Set-Location -LiteralPath $mobileRoot
    & npx.cmd expo prebuild --platform android --no-install --no-clean
    if ($LASTEXITCODE -ne 0) { throw 'Expo Android generation failed.' }
    $manifest = Get-Content -LiteralPath 'android\app\build.gradle' -Raw
    if ($manifest -notmatch 'applicationId\s+[''\"]kr\.hinoto\.lumen[''\"]' -or
        -not $manifest.Contains('// LumenDB local upload signing')) {
        throw 'Android package or signing configuration was not generated.'
    }
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    $outputRoot = (Resolve-Path -LiteralPath $OutputDirectory).Path
    $logPath = Join-Path $outputRoot 'android-play-build.log'
    Set-Location -LiteralPath (Join-Path $mobileRoot 'android')
    Write-Host 'Building upload-signed Android App Bundle and review APK...'
    # Windows PowerShell treats native stderr warnings as ErrorRecords.
    # Gradle's exit code determines whether the native build failed.
    $ErrorActionPreference = 'Continue'
    try {
        & .\gradlew.bat :app:bundleRelease :app:assembleRelease `
            '-PreactNativeArchitectures=arm64-v8a,x86_64' --console=plain --no-daemon `
            '-Dorg.gradle.workers.max=2' '-Dorg.gradle.jvmargs=-Xmx3g -XX:MaxMetaspaceSize=1024m' `
            *> $logPath
        $buildExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = 'Stop'
    }
    if ($buildExitCode -ne 0) {
        Get-Content -LiteralPath $logPath -Tail 60
        throw "Android build failed. See $logPath"
    }
    $bundle = Join-Path $mobileRoot 'android\app\build\outputs\bundle\release\app-release.aab'
    $verification = & (Join-Path $jdk 'bin\jarsigner.exe') '-J-Duser.language=en' '-J-Duser.country=US' -verify $bundle 2>&1
    if ($LASTEXITCODE -ne 0 -or ($verification -join "`n") -notmatch 'jar verified') {
        throw 'App Bundle signature verification failed.'
    }
    $version = (Get-Content -LiteralPath (Join-Path $mobileRoot 'package.json') -Raw | ConvertFrom-Json).version
    $destination = Join-Path $outputRoot "LumenDB-$version.aab"
    Copy-Item -LiteralPath $bundle -Destination $destination -Force
    Copy-Item -LiteralPath (Join-Path $mobileRoot 'android\app\build\outputs\apk\release\app-release.apk') `
        -Destination (Join-Path $outputRoot 'LumenDB-preview.apk') -Force
    Get-Content -LiteralPath $logPath -Tail 3
    Write-Host "App Bundle: $destination"
    Write-Host "SHA-256: $((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash)"
} finally {
    Set-Location -LiteralPath $location.Path
    foreach ($name in $previous.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
    $environment.Clear()
}
