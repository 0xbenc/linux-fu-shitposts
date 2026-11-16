# Later documentation procedure, not the original host-deployed script.
# Requires elevated 64-bit Windows PowerShell 5.1 and a fresh in-box SSH server.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z_][a-z0-9_.-]*$')]
    [string]$WindowsUser,

    [Parameter(Mandatory = $true)]
    [string]$PublicKeyPath
)

$ErrorActionPreference = 'Stop'
if ($WindowsUser -cne $WindowsUser.ToLowerInvariant()) {
    throw 'Use the lowercase Windows account name in the SSH configuration.'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Open 64-bit Windows PowerShell with Run as administrator, then retry.'
}
if (-not [Environment]::Is64BitProcess) { throw 'Use 64-bit Windows PowerShell.' }

# Intentionally narrow: one existing local administrator, with no existing setup.
$account = Get-LocalUser -Name $WindowsUser
if (-not $account.Enabled) { throw 'The selected local Windows account is disabled.' }
$admins = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$system = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
$members = @(Get-LocalGroupMember -SID $admins)
if ($account.SID.Value -notin @($members | ForEach-Object { $_.SID.Value })) {
    throw 'This procedure requires a direct member of the local Administrators group.'
}

$sshDir = Join-Path $env:ProgramData 'ssh'
$binDir = Join-Path $env:WINDIR 'System32\OpenSSH'
$server = Join-Path $binDir 'sshd.exe'
$keygen = Join-Path $binDir 'ssh-keygen.exe'
$shell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$registry = 'HKLM:\SOFTWARE\OpenSSH'
$rule = 'Windows-SSH-2222-Private'
$service = Get-Service sshd
if ($service.Status -ne 'Stopped') { throw 'sshd must be stopped before initial setup.' }
if (Test-Path -LiteralPath $sshDir) {
    throw 'ProgramData\ssh already exists. Inspect and adapt it; this script will not overwrite it.'
}
if (Get-ItemProperty -Path $registry -Name DefaultShell -ErrorAction SilentlyContinue) {
    throw 'An OpenSSH DefaultShell is already set. Preserve it and configure manually.'
}
if (Get-NetFirewallRule -Name $rule -ErrorAction SilentlyContinue) {
    throw 'The custom port-2222 firewall rule already exists. Inspect it before continuing.'
}
if (Get-NetTCPConnection -State Listen -LocalPort 2222 -ErrorAction SilentlyContinue) {
    throw 'Port 2222 is already listening. Identify its owner before continuing.'
}
foreach ($file in @($server, $keygen, $shell)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required file missing: $file" }
}

$PublicKeyPath = (Resolve-Path -LiteralPath $PublicKeyPath).ProviderPath
$lines = @(Get-Content -LiteralPath $PublicKeyPath | Where-Object { $_.Trim() -and -not $_.Trim().StartsWith('#') })
if ($lines.Count -ne 1) { throw 'Supply one OpenSSH public key, on one line.' }
$key = $lines[0].Trim()
if ($key -notmatch '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(256|384|521)|sk-ssh-ed25519@openssh.com|sk-ecdsa-sha2-nistp256@openssh.com) [A-Za-z0-9+/]+={0,3}( .*)?$') {
    throw 'Expected an OpenSSH public-key line, not a private key or authorized_keys options.'
}
& $keygen -l -f $PublicKeyPath
if ($LASTEXITCODE -ne 0) { throw 'ssh-keygen could not parse the supplied public key.' }

# All preflight checks above are read-only. Mutations start here.
# The caller keeps this output for recovery if a later step fails.
$previousStartMode = (Get-CimInstance Win32_Service -Filter "Name='sshd'").StartMode
$defaultRule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
Write-Output "Previous sshd start mode: $previousStartMode"
if ($defaultRule) { Write-Output "Previous default firewall rule enabled: $($defaultRule.Enabled)" }

New-Item -Path $sshDir -ItemType Directory | Out-Null
$config = Join-Path $sshDir 'sshd_config'
@"
Port 2222
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
AllowUsers $WindowsUser
AuthorizedKeysFile .ssh/authorized_keys
Subsystem sftp sftp-server.exe
Match Group administrators
    AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys
"@ | Set-Content -LiteralPath $config -Encoding ascii

$authorizedKeys = Join-Path $sshDir 'administrators_authorized_keys'
[IO.File]::WriteAllText($authorizedKeys, $key + "`r`n", [Text.UTF8Encoding]::new($false))
& $keygen -A
if ($LASTEXITCODE -ne 0) { throw 'Host-key generation failed.' }

# Apply the effective fix from the incident to both kinds of sensitive file.
# Use SIDs so the ACL does not depend on translated Windows group names.
$privateFiles = @($authorizedKeys) + @(Get-ChildItem -LiteralPath $sshDir -Filter 'ssh_host_*_key' -File | ForEach-Object { $_.FullName })
foreach ($file in $privateFiles) {
    $acl = New-Object Security.AccessControl.FileSecurity
    $acl.SetOwner($admins)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in @($admins, $system)) {
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow')))
    }
    Set-Acl -LiteralPath $file -AclObject $acl
}

New-Item -Path $registry -Force | Out-Null
New-ItemProperty -Path $registry -Name DefaultShell -Value $shell -PropertyType String -Force | Out-Null
& $server -t
if ($LASTEXITCODE -ne 0) { throw 'sshd configuration validation failed; service was not started.' }

# The capability's rule permits port 22; our new rule permits the actual server port.
# Changing the port-22 rule can affect an existing WSL forwarding arrangement.
if ($defaultRule) { Disable-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' | Out-Null }
New-NetFirewallRule -Name $rule -DisplayName 'Windows SSH (2222, private networks)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 2222 -Profile Private -Program $server | Out-Null
Set-Service sshd -StartupType Automatic
Start-Service sshd
Get-Service sshd
Get-NetTCPConnection -State Listen -LocalPort 2222 | Select-Object LocalAddress, LocalPort
& $keygen -l -f (Join-Path $sshDir 'ssh_host_ed25519_key.pub')
if ($LASTEXITCODE -ne 0) { throw 'Could not print the server ED25519 fingerprint.' }
Write-Output 'Server started. Compare the fingerprint and test login from your actual client.'
