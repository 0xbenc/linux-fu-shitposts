# SSH straight into Windows, leave WSL on port 22

**Tested Windows setup:** Windows 10 22H2 / build 19045, Windows PowerShell 5.1, in-box OpenSSH 9.5, and an existing Ubuntu WSL SSH server. Wi-Fi and Tailscale were classified as Private networks. Ubuntu's exact release was not recorded; this fix runs on Windows, not inside the distro. Windows 11 has not been tested for this post.

The old route was SSH into WSL, then launch PowerShell to reach Windows. Running Windows' own SSH server on **2222** gives it a separate front door:

```text
ssh -p 22   linux-user@WSL-ADDRESS      -> Linux shell
ssh -p 2222 winuser@WINDOWS-ADDRESS    -> Windows PowerShell
```

The addresses may differ. Keeping WSL reachable still depends on its existing networking and forwarding setup.

## Before you start

Use **64-bit Windows PowerShell → Run as administrator**. You need Git for the clone command below, an existing, enabled **local Windows account directly in the Administrators group**, Windows Update access to install the feature, and the public key belonging to your connecting client. This procedure allows only that Windows account to log in. It does not create an account.

Have a working console or existing WSL session available until the new login works. The bundled script is for a **fresh Windows SSH server**: it refuses an existing `C:\ProgramData\ssh` directory or a running server. For an existing installation, [adapt the individual changes](ai-context.md#existing-installations-and-other-accounts) rather than deleting its configuration or keys.

## 1. Bring over your client's public key

On the computer you will connect **from**, locate the public key paired with your private key. For example:

```sh
cat ~/.ssh/id_ed25519.pub
```

Copy that one `ssh-ed25519 ...` line into a text file on Windows, such as `$env:USERPROFILE\client-key.pub`. If WSL already accepts the same client, the corresponding line in its `~/.ssh/authorized_keys` can be used instead. Select the intended key; do not blindly import every authorized key or discard its restrictions.

**The Windows server needs the public key. Your client's private key stays on the client.** Server host keys, created below, are a separate set of keys identifying this Windows machine.

## 2. Install and configure Windows SSH

In elevated Windows PowerShell, clone this repo and enter the post directory. The HTTPS clone does not require a GitHub SSH key:

```powershell
Set-Location $env:USERPROFILE
git clone https://github.com/0xbenc/linux-fu-shitposts.git
Set-Location .\linux-fu-shitposts\posts\2026-11-16-windows-ssh-alongside-wsl

$ErrorActionPreference = 'Stop'
Add-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0'
```

If installation requests a restart, finish it before continuing. Substitute your **Windows** login name for `winuser`; it need not match your WSL username. Verify it with `Get-LocalUser` if unsure. Then run:

```powershell
# Runs in a child process; does not change your saved execution policy.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\files\Set-UpWindowsSsh.ps1 -WindowsUser winuser -PublicKeyPath "$env:USERPROFILE\client-key.pub"
if ($LASTEXITCODE -ne 0) { throw 'Setup failed. Read the error before continuing.' }
```

The script sets port 2222, public-key-only login, PowerShell as the shell, automatic service startup, and a firewall rule for **Private profiles only**. It fixes permissions on the authorized-key file **and the server's private host keys** before starting the service. It disables the capability's default port-22 firewall rule; inspect that rule first if your WSL forwarding arrangement uses it. It does not change WSL, port proxies, router forwarding, or Tailscale policy.

This script is a later, generalized replay of the successful changes. Its syntax and isolated ACL checks were validated; it was **not rerun as a full installer** on the working machine. The original changes and login tests are [recorded separately](ai-context.md#validation-and-practical-limits).

## 3. Connect and prove you reached Windows

On Windows, find the address of the interface your client can reach:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
    Select-Object InterfaceAlias, IPAddress
Get-NetConnectionProfile | Select-Object InterfaceAlias, NetworkCategory
```

Use the Wi-Fi/Ethernet address on the same LAN, or the Windows Tailscale address from another permitted tailnet device. A Private-profile firewall rule will not apply to an interface classified Public; [check the profile and route](ai-context.md#connection-times-out) rather than opening every profile.

From your client, replacing `WINDOWS-ADDRESS` and `winuser`:

```sh
ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes -p 2222 winuser@WINDOWS-ADDRESS
```

Compare the first-connection fingerprint with the ED25519 fingerprint printed by setup. You can print it again in elevated Windows PowerShell:

```powershell
& "$env:WINDIR\System32\OpenSSH\ssh-keygen.exe" -l -f "$env:ProgramData\ssh\ssh_host_ed25519_key.pub"
```

After signing in, run:

```powershell
whoami
$env:OS
$PSVersionTable.PSVersion
```

Expect your Windows machine/account, `Windows_NT`, and a PowerShell version. **Verified in this incident:** native Windows login over loopback and the machine's Tailscale IP; WSL-to-Windows login over the machine's LAN IP. A connection from a separate physical device and login after reboot remain untested. `Automatic` startup is configured, not a completed reboot test.

## If the service refuses to start

The actual failure was **“Permissions ... are too open”**, followed by **“no hostkeys available”**. It concerned the server's private host keys, not the client's login key. A valid configuration and a successful interactive debug run had not proved the Windows service could use those keys. The bundled script includes the repair; [diagnosis and targeted repair](ai-context.md#service-startup-fails) are in the full context.

## Undo

From a console or your still-working WSL route, in elevated Windows PowerShell:

```powershell
Stop-Service sshd
Set-Service sshd -StartupType Disabled
Remove-NetFirewallRule -Name 'Windows-SSH-2222-Private'
```

That disables this Windows endpoint while retaining its configuration and server identity. It disconnects Windows SSH sessions. For shell-setting cleanup, optional feature removal, and the default firewall rule, use the [scoped rollback](ai-context.md#rollback-and-recovery). Do not delete the whole SSH directory as a routine uninstall step.

[Full investigation, configuration, validation and recovery](ai-context.md)
