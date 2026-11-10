# 업로드 키스토어 비밀번호를 입력받아 이 PC·계정 전용으로 암호화한 자격 증명 XML을 만든다.
# 다른 PC에서 만든 XML은 복호화되지 않으므로, PC를 옮기면 이 스크립트로 다시 만든다.
[CmdletBinding()]
param(
    [string]$StoreFile = 'C:\Hinoto\lumen-upload.keystore',
    [string]$KeyAlias = 'HInoto_key',
    [string]$OutputPath = 'C:\Hinoto\lumen-upload.credentials.xml'
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $StoreFile -PathType Leaf)) { throw "Keystore not found: $StoreFile" }

$jdk = $env:JAVA_HOME
if (-not $jdk -or -not (Test-Path -LiteralPath (Join-Path $jdk 'bin\keytool.exe'))) {
    $jdk = 'C:\Program Files\Android\Android Studio\jbr'
}
$keytool = Join-Path $jdk 'bin\keytool.exe'
if (-not (Test-Path -LiteralPath $keytool)) { throw 'keytool not found. Set JAVA_HOME to a JDK.' }

$storePassword = Read-Host 'Keystore password' -AsSecureString
$keyPassword = Read-Host 'Key password (Enter = same as keystore)' -AsSecureString
if ($keyPassword.Length -eq 0) { $keyPassword = $storePassword.Copy() }

function Plain([Security.SecureString]$s) {
    ([PSCredential]::new('x', $s)).GetNetworkCredential().Password
}

# 키스토어 비밀번호와 별칭이 맞는지 확인한다. 비밀번호는 환경변수로만 전달한다.
$env:LUMEN_CHECK_STOREPASS = Plain $storePassword
try {
    & $keytool -list -keystore $StoreFile -alias $KeyAlias -storepass:env LUMEN_CHECK_STOREPASS | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Keystore password or alias is wrong.' }
} finally {
    Remove-Item Env:\LUMEN_CHECK_STOREPASS -ErrorAction SilentlyContinue
}

[pscustomobject]@{
    StoreFile = (Resolve-Path -LiteralPath $StoreFile).Path
    StorePassword = $storePassword
    KeyAlias = $KeyAlias
    KeyPassword = $keyPassword
} | Export-Clixml -LiteralPath $OutputPath

Write-Host "Saved $OutputPath (decryptable only by this Windows account on this PC)."
