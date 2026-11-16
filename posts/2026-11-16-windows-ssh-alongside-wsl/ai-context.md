# Windows SSH on 2222 beside WSL — AI context dump

**Incident and documentation date:** 2026-11-16. **Tested setup:** Windows 10 22H2 / build 19045, Windows PowerShell `5.1.19041.6456`, in-box OpenSSH server file version `9.5.4.1` / product `OpenSSH_9.5p1 for Windows`, existing Ubuntu WSL with SSH. The Ubuntu release was not collected. Windows configuration, rather than Linux distribution behavior, is the subject of this post. No Windows 11 or domain-account test is claimed.

## Current result and remaining work

Windows' `sshd` runs as LocalSystem, listens on port **2222**, and has `StartMode=Auto`. Its default shell is Windows PowerShell. The selected existing Windows administrator can authenticate with the same client key already authorized by WSL. Password and keyboard-interactive authentication are disabled. A new firewall rule allows the Windows server executable on TCP/2222 for Private network profiles.

Three public-key authentication checks succeeded:

| Client and destination | Observed result | What it establishes |
| --- | --- | --- |
| Windows client → `127.0.0.1:2222` | Windows account, PowerShell version, `Windows_NT` | Service, selected key and Windows shell worked locally |
| Windows client → this machine's Tailscale IP, port 2222 | Windows account | Login through that destination address worked from the same machine |
| Ubuntu WSL client → this machine's LAN IP, port 2222 | Windows account | WSL-to-Windows routing and key login worked |

The second check is **not** a separate tailnet peer test. None establishes another physical client's firewall path, tailnet policy, router forwarding, public-internet reachability, or post-reboot availability. No reboot or independent remote-device test was performed. The user did not separately confirm a remote Windows login.

WSL's existing port-22 loopback listeners remained present. There was no edit to WSL's SSH configuration, its forwarding, or the router. We did not independently retest the user's original remote-to-WSL route. The Windows default OpenSSH port-22 firewall rule was disabled; that is potentially relevant on machines whose WSL forwarding depends on that same rule.

## User intent and scope

The user normally SSHed into WSL and invoked PowerShell there to control Windows. They requested direct SSH access to Windows. Port 2222 was chosen to avoid competing with the existing port-22 route. The user later requested a depersonalized post explaining the actual work in enough detail to reproduce it.

Documentation did not authorize reinstalling the working server, rebooting, changing network profiles, or exposing a router port. The later bundled script was reviewed and syntax checked without applying it to the live installation. No commit, push or publication is part of this documentation task.

## Environment and initial observations

Windows had the OpenSSH **client** tools, but no `sshd` executable or service. The initial `Get-WindowsCapability -Online` call failed because the session was not elevated. The Windows account used for setup could approve UAC elevation.

Port 22 had listeners on `127.0.0.1` and `::1` owned by `wslrelay.exe`; this was not an existing Windows SSH server. No portproxy entries were returned. These local observations do not explain every component of the user's existing remote WSL route.

The active Wi-Fi and Tailscale connection profiles were Private. Their actual addresses, network names and tailnet hostname are deliberately omitted. The server's local Windows username differed from the WSL username. One Ed25519 public key was already in the WSL account's `authorized_keys`. A matching client private key also already existed on Windows, allowing a native loopback login test without creating or transferring another client key.

The machine had no relevant hardware dependency; CPU, GPU, memory and storage inventories are omitted.

## Three different key roles

| Item | Location / owner | Purpose |
| --- | --- | --- |
| Client private key | Connecting computer, held by its user | Proves the person connecting possesses an authorized key |
| Authorized public key | Windows `administrators_authorized_keys` | Tells the server which client key to accept |
| Server private host keys | Windows `ProgramData\ssh\ssh_host_*_key` | Identify the Windows server to clients |

Only the **public** half of the existing client key was imported from WSL. The private key was not needed for that import. Its preexisting Windows copy was used for the local client test. The server generated its own host keys with `ssh-keygen -A`.

Outbound GitHub/Gitea access is a separate client configuration. Enabling inbound Windows SSH does not install a Git identity, authorize a Git hosting account, copy a private key, or automatically make agent keys available in every later SSH session. The session's later Git checks are outside this post's fix.

## Investigation and failed attempts

1. Inspected Windows services, installed binaries, listeners, interface profiles and the existing WSL authorized public key. Chose 2222 because WSL already had local port-22 listeners.
2. Prepared a Windows setup script, then launched an elevated PowerShell process through UAC. Installation and service/firewall changes require elevation; being signed into an administrator account alone had not elevated the original process.
3. Installed `OpenSSH.Server~~~~0.0.1.0`. The installer reported `RestartNeeded=False`. Created the server directory, configuration and administrator authorized-key file. Imported the selected public key, set its ACL, chose PowerShell in the registry, generated host keys and validated configuration with `sshd -t`.
4. Disabled the capability's default port-22 firewall rule, added the Private-profile port-2222 rule, and set automatic startup. `Restart-Service sshd` failed; the service exited with code 1067. A later `Start-Service` attempt failed too. Syntax validation had not established successful service startup.
5. Checked Service Control Manager and OpenSSH event channels. The System log showed unexpected service termination, but the OpenSSH Admin/Operational logs were empty. Repeating the same start command added no useful diagnosis.
6. Ran an elevated foreground diagnostic, `sshd -ddd -E <local-debug-log>`. It loaded the configuration and keys and listened on IPv4 and IPv6 port 2222. The diagnostic process was then stopped. **That interactive administrator context was not the failing LocalSystem service context.** Its success did not clear the service's host-key permission checks.
7. Temporarily changed the service binary command line to add `-E C:\ProgramData\ssh\logs\startup.log`. Starting the actual service then produced the useful failure: all three private host keys were rejected as too broadly accessible, followed by `sshd: no hostkeys available -- exiting.` See the [preserved failure log](evidence/service-startup-failure.txt).
8. Replaced the ACLs of `ssh_host_rsa_key`, `ssh_host_ecdsa_key` and `ssh_host_ed25519_key`: owner Administrators, inheritance disabled, explicit FullControl only for Administrators and SYSTEM. Restored the service binary path to the plain in-box `sshd.exe` path. The service started successfully.
9. Performed the three login checks listed above. Queried the service again: `Running`, `Auto`. Printed its ED25519 host fingerprint for verification, but did not publish that machine-specific fingerprint.

### What the evidence proves

The diagnostic explicitly identifies rejected **private host keys**. Startup succeeded after the ACL repair and restoration of the ordinary service command line. This supports the host-key permission diagnosis. The earlier authorized-key file ACL was already sufficient for the later successful login.

The initial setup created the SSH directory before generating host keys. Its directory ACL included read access for Authenticated Users. That is a plausible route for the broad key permissions; the investigation did not preserve a complete pre-repair ACL capture for every host key. Do not invent one or claim a particular Windows Update caused the failure. Microsoft's [permissions/startup article](https://learn.microsoft.com/en-us/troubleshoot/windows-server/system-management-components/error-1053-1067-7034-after-update-openssh-doesnt-start) describes related failures, but its update chronology is not evidence of this incident's cause.

An account's membership in Administrators does **not** prove that account is Windows' built-in RID-500 Administrator. The reusable instructions support an existing local administrator through group membership, without relying on that special account.

## Final implementation

### Server configuration

The final host configuration is reproduced below with its one allowed login replaced by `winuser`. That name is a placeholder, not a required account:

```text
Port 2222
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
AllowUsers winuser
AuthorizedKeysFile .ssh/authorized_keys
Subsystem sftp sftp-server.exe
Match Group administrators
    AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys
```

It is stored at `%ProgramData%\ssh\sshd_config`. Windows account names in this configuration should be lowercase. `AllowUsers` restricts login to the selected account; the `Match Group` block supplies the key-file location for administrator accounts. Port 2222 distinguishes endpoints; it is not an authentication control.

The standard administrator key file is **shared among administrator accounts** matching that block. It is not a per-user key store. This configuration's one-user allowlist limits who can use it. If expanding access, review that interaction instead of simply adding another username.

### Files, registry and service

| Object | Effective change |
| --- | --- |
| `OpenSSH.Server~~~~0.0.1.0` | Installed through Windows optional capabilities |
| `%ProgramData%\ssh\sshd_config` | Port, authentication, allowlist, key lookup and SFTP settings above |
| `%ProgramData%\ssh\administrators_authorized_keys` | Selected authorized public key; inheritance removed; Administrators/SYSTEM FullControl |
| `%ProgramData%\ssh\ssh_host_*_key` | Generated server identity; fixed owner and restricted ACLs |
| `HKLM:\SOFTWARE\OpenSSH`, string `DefaultShell` | `%WINDIR%\System32\WindowsPowerShell\v1.0\powershell.exe`, expanded to an absolute path |
| Windows `sshd` service | LocalSystem, normal in-box binary path, automatic startup, running |
| `Windows-SSH-2222-Private` firewall rule | Inbound allow, TCP/2222, enabled, Private profile, restricted to `sshd.exe` |
| `OpenSSH-Server-In-TCP` firewall rule | Disabled; its port-22 allowance did not match the new Windows port |

Both ACLs use the stable SIDs `S-1-5-32-544` (Administrators) and `S-1-5-18` (SYSTEM), avoiding translated group names. The deployed authorized-key repair removed inheritance and limited access to those principals. The later replay additionally sets its owner to Administrators, as the successful host-key repair did.

The firewall rule has no client-address restriction. On the host, both active profiles were Private. A Private profile is a Windows network category, **not** a restriction to RFC1918 source addresses or a guarantee of Tailscale-only access. The server listens on wildcard IPv4/IPv6 addresses; the rule controls the permitted profile and program. Tailnet policy and routing remain separate requirements. The IPv6 listeners were observed; an IPv6 login was not tested.

The temporary service `-E` command line was removed. Its local diagnostic files were not required for operation and are not installed by the replay. The server's private keys, authorized client key, actual addresses and host fingerprint are not bundled.

## Reproduce and adapt

Start with the [human guide](human.md). All Windows setup commands run in elevated **64-bit Windows PowerShell**, from this post directory. Client commands run on the connecting computer. Avoid mixing Bash and PowerShell quoting or assuming the WSL username is a Windows account.

[Set-UpWindowsSsh.ps1](files/Set-UpWindowsSsh.ps1) is a **later documentation implementation**, not a byte-identical copy of the original setup script. Its differences are deliberate:

- Takes an explicit local Windows username and public-key path rather than embedding personal values or automatically importing all WSL keys.
- Requires a directly enrolled, enabled local administrator and rejects a running service, an existing server directory, an existing default-shell value, a conflicting custom firewall rule or an occupied port 2222. It validates input before writing server files.
- Accepts one ordinary OpenSSH public-key line and verifies its parsing with `ssh-keygen`. It does not import `authorized_keys` restrictions or private keys.
- Applies the successful host-key ACL repair **before** attempting startup. The original first attempt did not.
- Sets Administrators ownership on both host private keys and the authorized-key file.
- Leaves the service's installed binary command line alone; it does not recreate the incident's diagnostic detour.

Installation of the optional capability is a separate, explicit step in the human guide. The script does not install a different OpenSSH distribution. If an administrator or Windows policy already created the server directory, inspect it manually; do not remove it to satisfy the guard. This script intentionally is **not idempotent**. A partial run leaves state for inspection and will fail the next preflight. It has no automatic rollback; use the recovery section after an error rather than pretending a retry is safe.

The service start mode and default firewall rule's enabled state are printed before mutation. Retain that output if you want to reverse those specific changes. The script contains no client private key or server host key, and needs no external installer beyond Windows' capability mechanism.

### Existing installations and other accounts

For an existing server, retain a working session and first back up the configuration, relevant public-key file, ACLs, service start mode, default shell value and affected firewall rules. Merge the individual directives; do not replace all policy with the sample. Check existing `Match` blocks, other users, SFTP requirements and enterprise policy. Do not regenerate or delete existing host keys to change the port.

For a standard local user, the key usually belongs in that user's `%USERPROFILE%\.ssh\authorized_keys`, with that user's appropriate ACLs; this post's administrator-only script is not the right installer. Domain accounts, Microsoft-connected account edge cases, nested group membership and non-English group matching were not qualified in the incident. SIDs make the ACL operations language-independent, but they do not constitute a localized-Windows end-to-end test.

If copying a key from WSL, read only the selected public-key line from the correct Linux user's `authorized_keys`. The incident had one unrestricted key. Keys with `from=`, `command=`, or other options need deliberate treatment: stripping options changes what that key authorizes. Do not silently turn a restricted Linux key into unrestricted Windows login permission.

## Troubleshooting

### Service startup fails

In elevated Windows PowerShell:

```powershell
$server = "$env:WINDIR\System32\OpenSSH\sshd.exe"
& $server -t
if ($LASTEXITCODE -ne 0) { throw 'Fix the reported configuration error first.' }
Get-Service sshd
Get-WinEvent -LogName 'OpenSSH/Operational' -MaxEvents 10 -ErrorAction SilentlyContinue
Get-WinEvent -LogName 'OpenSSH/Admin' -MaxEvents 10 -ErrorAction SilentlyContinue
```

A clean `-t` result is only a configuration check. Empty OpenSSH logs were observed in this incident. An interactive `-ddd` listener can also succeed under a different security context; stop it before attempting the real service on the same port.

To obtain a file log from the **actual service**, first record its current command line. The following diagnostic assumes the unmodified in-box service path; adapt it if your service is different. It deliberately stops the service and will disconnect its sessions:

```powershell
Get-CimInstance Win32_Service -Filter "Name='sshd'" |
    Select-Object PathName, StartName
Stop-Service sshd -ErrorAction SilentlyContinue
New-Item "$env:ProgramData\ssh\logs" -ItemType Directory -Force | Out-Null
$debugCommand = "$env:WINDIR\System32\OpenSSH\sshd.exe -E $env:ProgramData\ssh\logs\startup.log"
sc.exe config sshd binPath= $debugCommand
if ($LASTEXITCODE -ne 0) { throw 'Could not configure service logging.' }
Start-Service sshd -ErrorAction Continue
Get-Content "$env:ProgramData\ssh\logs\startup.log" -Tail 60
```

This reproduces the diagnostic used on the standard `C:\Windows` / `C:\ProgramData` paths, which contain no spaces. A custom Windows/ProgramData path containing spaces requires separately quoted executable/log arguments in the service command line. Do not paste it unchanged there.

If the log specifically rejects the host private keys as too broadly accessible, inspect their ACLs, then apply the targeted repair below. It does not delete keys or change their identity:

```powershell
$admins = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$system = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
Get-ChildItem "$env:ProgramData\ssh\ssh_host_*_key" | ForEach-Object {
    Get-Acl -LiteralPath $_.FullName | Format-List Owner, AccessToString
    $acl = New-Object Security.AccessControl.FileSecurity
    $acl.SetOwner($admins)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in @($admins, $system)) {
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow')))
    }
    Set-Acl -LiteralPath $_.FullName -AclObject $acl
}

# Restore the ordinary in-box service command line after diagnosis.
Stop-Service sshd -ErrorAction SilentlyContinue
sc.exe config sshd binPath= "$env:WINDIR\System32\OpenSSH\sshd.exe"
if ($LASTEXITCODE -ne 0) { throw 'Could not restore the service path.' }
Start-Service sshd
```

Do not use that ACL replacement on an unrelated folder tree. If a service still fails, read the new error rather than recursively resetting all Windows or SSH permissions.

### Permission denied (publickey)

The server was reached; investigate account/key authorization. Check the **Windows** username and `AllowUsers`, the public key paired with the offered client private key, the administrator key-file location and ACL, and that the key occupies one line. Public-key files should be ASCII or UTF-8 without a BOM, not UTF-16. The bundled script writes UTF-8 without a BOM.

From the client:

```sh
ssh -vv -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes -p 2222 winuser@WINDOWS-ADDRESS
```

Replace both placeholders. Inspect which key is offered; do not fix this by copying a private key into `administrators_authorized_keys`. `BatchMode=yes` is useful for a noninteractive test with an already available key or agent; it will not prompt to unlock a passphrase-protected key. The human guide's interactive command allows that prompt.

### Connection times out

Check listener, effective interface profile, rule, address and route separately:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 2222
Get-NetConnectionProfile | Select-Object InterfaceAlias, NetworkCategory
Get-NetFirewallRule -Name 'Windows-SSH-2222-Private' |
    Select-Object Enabled, Profile, Direction, Action
Get-NetFirewallRule -Name 'Windows-SSH-2222-Private' | Get-NetFirewallPortFilter
Get-NetFirewallRule -Name 'Windows-SSH-2222-Private' | Get-NetFirewallApplicationFilter
```

The listener should be the Windows server, not a leftover foreground diagnostic. The source host used Private profiles for Wi-Fi and Tailscale. Discover your own profiles: a Public classification means this rule does not apply. Only mark a network Private if it is a network you intend to trust; otherwise design a narrowly scoped rule appropriate to that interface and permitted clients. Do not solve the mismatch by disabling the firewall.

For Tailscale, use the **Windows host's** tailnet address and verify peer connectivity and tailnet access policy. A WSL tailnet node, if one exists separately, is a different destination. Same-host success does not validate another peer's permissions. This procedure does not open a router port or publish SSH on the internet.

### Connection refused, or the wrong shell appears

Refused usually means nothing is accepting the connection at that address/port, or an intermediate device actively rejected it. Check `Get-Service sshd`, the listener and the exact destination. If you reach a Linux shell, check that you used 2222 and the Windows address.

If you reach Windows `cmd.exe`, inspect `HKLM:\SOFTWARE\OpenSSH\DefaultShell`. The deployed value selected built-in Windows PowerShell 5.1, not `pwsh.exe`. Installing PowerShell 7 alone does not change that value. Restarting `sshd` after changing service settings disconnects active Windows SSH sessions, so arrange another access path first.

## Validation and practical limits

The [redacted observation record](evidence/observations.json) separates source-session results from the later documentation checks. The original service failure text is preserved independently. No raw transcript with usernames, addresses, public-key material or fingerprints is published.

Original live validation: installation returned no restart requirement; service configuration passed `sshd -t`; host-key repair allowed service startup; service state/start mode were Running/Auto; key login produced the expected Windows identity and PowerShell output; Windows and WSL clients completed the three checks in the opening table. The native client specified the preexisting private key, `IdentitiesOnly=yes` and `BatchMode=yes`. Its test-specific known-hosts file used `StrictHostKeyChecking=accept-new`; that recorded a newly seen key but did not independently authenticate its fingerprint. The public guide improves that step by asking readers to compare the locally printed fingerprint.

Documentation validation uses the installed Windows PowerShell parser on the bundled scripts and every `powershell` fenced block, an isolated execution of the setup script's ACL loop with `Set-Acl` replaced by a recorder, local Markdown path/anchor checks, whitespace checks, and a privacy scan against the incident's personal identifiers. The ACL check inspects the resulting owner, protected inheritance, two allowed principals and access rights without applying permissions to any file. A static review checks that the replay selects both key-file categories before startup and that the documented files are present. See [the check report](evidence/documentation-validation.json) for actual results.

Reproduce the parser and isolated ACL checks from this post directory, without elevation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\files\check-docs.ps1
if ($LASTEXITCODE -ne 0) { throw 'Documentation checks failed.' }
```

These checks do **not** establish that the generalized script has completed on another clean Windows installation. Neither the setup script, its diagnostic snippets nor rollback commands were executed against the working server as part of writing the post. No SFTP transfer, IPv6 login, passphrase/agent workflow, sleep/resume or reboot was tested. Automatic startup and SFTP configuration describe intended behavior, with those limits intact.

## Rollback and recovery

Keep a local console or independently working WSL route available. Do not stop the Windows SSH service from your only remaining access path. This section is a documented procedure, **not** a rollback performed on the repaired machine.

### Disable only the new endpoint

In elevated Windows PowerShell:

```powershell
Stop-Service sshd
Set-Service sshd -StartupType Disabled
Remove-NetFirewallRule -Name 'Windows-SSH-2222-Private'
```

This retains server configuration, authorized public keys and host identity, but disables Windows SSH. It does not edit WSL. It also does not automatically restore a port-22 firewall rule needed by an unusual WSL forwarding arrangement; inspect your recorded baseline before changing that rule.

### Remove the new default shell setting

The fresh-server replay refuses a preexisting `DefaultShell` property, so its new value can be removed when undoing that replay:

```powershell
Remove-ItemProperty -Path HKLM:\SOFTWARE\OpenSSH -Name DefaultShell
```

For an existing installation configured manually, restore its saved value instead. Do not delete the entire OpenSSH registry key; the client or another configuration may use other properties. With no override, a later enabled server uses Windows' default shell behavior.

### Optional capability removal

If Windows' SSH server was installed only for this change and you intend to remove it:

```powershell
Remove-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0'
```

Check its returned restart requirement. Do not remove `OpenSSH.Client`; the client is separate and may be used by Git or other tools. Feature removal is not a promise to erase every configuration file. Keep host keys if you may reinstall and want the same server identity. Do not publish or copy their private contents into the repo.

### Default firewall rule and partial failures

The installed capability creates or uses `OpenSSH-Server-In-TCP`. The original setup disabled it because the Windows service moved to 2222. Do not blindly enable it during uninstall. If restoring a previous arrangement, restore the rule's saved enabled state, program, profile and port filters. If the rule was newly installed and nothing else uses it, it can remain disabled; inspect before removing it.

After a partial setup failure, first read the error and inspect service state. The script deliberately retains its files for diagnosis. Use `sshd -t`, the service log and targeted repair rather than deleting the directory and rerunning. If you decide to abandon the attempt, disable the endpoint as above; remove only files you have established were created by that attempt. Existing SSH configuration and host identity require a backup-aware recovery, not a recursive cleanup command.

## Sources and provenance

- [Microsoft: get started with OpenSSH for Windows](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse): optional capability, elevation and service setup.
- [Microsoft: Windows OpenSSH server configuration](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh-server-configuration): configuration path, default-shell registry value and administrator key-file behavior.
- [Microsoft: key-based authentication](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement): client/server key roles and administrator authorized-key permissions.
- [Microsoft: startup errors and permissions](https://learn.microsoft.com/en-us/troubleshoot/windows-server/system-management-components/error-1053-1067-7034-after-update-openssh-doesnt-start): related diagnostics, not proof that a specific update caused this incident.
- Source-session tool output and local setup/debug logs, summarized in [observations.json](evidence/observations.json). The original setup and repair scripts remain outside the publication tree. Their personal paths are not runtime dependencies of this post.

## Privacy treatment

Replaced or omitted the real Windows/WSL logins, machine name, home directory, LAN/WSL/tailnet addresses, tailnet DNS name, Wi-Fi network name, key filenames/comments/material, host fingerprints, process identifiers and unrelated Git hosting details. `winuser`, `WINDOWS-ADDRESS`, `WSL-ADDRESS` and `id_ed25519` are explanatory examples. They must be replaced or discovered on the reader's machine.

Kept the actual port, versions, capability/service/rule names, Windows standard paths and security principal SIDs because they explain or reproduce the fix. The failure log has no host identity or key bytes; it retains only standard private-key filenames. The JSON observation record is an explicitly redacted, curated derivative, not a byte-identical raw session capture. Public repo attribution remains intact.
