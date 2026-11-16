# Windows SSH replay

`Set-UpWindowsSsh.ps1` configures a fresh in-box Windows SSH server after installation of the optional server capability. Read [the human guide](../human.md) before running it.

Inputs are an existing local administrator's lowercase account name and one client **public** key file. It writes the configuration, authorized-key file, host-key ACLs, shell registry setting and firewall rule, then starts the server on 2222.

This is a later, depersonalized procedure derived from the successful changes, including the host-key permission correction. It is not the original script or a newly verified clean-machine installation. It refuses an existing server directory or active service and is not intended for repeated runs. It has no automatic rollback after a partial failure. See [implementation and validation](../ai-context.md#reproduce-and-adapt) and [recovery](../ai-context.md#rollback-and-recovery).

No client private keys, server host keys, original public keys or personal configuration are included.

`check-docs.ps1` parses both PowerShell scripts and the post's PowerShell code blocks. It executes the setup script's ACL loop against two fixture names, replacing `Set-Acl` with a recorder, then checks the resulting security descriptors. It does not install anything, start a server, or change permissions. Run it without elevation using the command in [validation](../ai-context.md#validation-and-practical-limits).
