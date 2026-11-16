# Parse documentation and check the actual ACL loop without applying any ACLs.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$post = Split-Path -Parent $PSScriptRoot
$scriptFiles = @(Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1' -File)
$blockCount = 0
foreach ($file in $scriptFiles) {
    $tokens = $null
    $errors = $null
    [void][Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw "$($file.Name): $($errors -join '; ')" }
}
foreach ($file in Get-ChildItem -LiteralPath $post -Filter '*.md' -File) {
    $markdown = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
    foreach ($match in [regex]::Matches($markdown, '(?ms)^```powershell\r?\n(.*?)^```')) {
        $tokens = $null
        $errors = $null
        [void][Management.Automation.Language.Parser]::ParseInput($match.Groups[1].Value, [ref]$tokens, [ref]$errors)
        if ($errors.Count) { throw "$($file.Name) block $blockCount : $($errors -join '; ')" }
        $blockCount++
    }
}

$setup = Join-Path $PSScriptRoot 'Set-UpWindowsSsh.ps1'
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($setup, [ref]$tokens, [ref]$errors)
$loops = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.ForEachStatementAst] -and
    $node.Condition.Extent.Text -eq '$privateFiles'
}, $true))
if ($loops.Count -ne 1) { throw 'Expected one ACL loop over the selected sensitive files.' }

# This function shadows the real cmdlet inside this process. No file is touched.
$script:recordedAcls = @()
function Set-Acl {
    param([string]$LiteralPath, [Security.AccessControl.FileSecurity]$AclObject)
    $script:recordedAcls += [pscustomobject]@{ Path = $LiteralPath; Acl = $AclObject }
}
$admins = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$system = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
$privateFiles = @('fixture-authorized-keys', 'fixture-server-host-key')
& ([scriptblock]::Create($loops[0].Extent.Text))
if ($script:recordedAcls.Count -ne 2) { throw 'Both fixture files must receive an ACL.' }
foreach ($entry in $script:recordedAcls) {
    if ($entry.Path -notin $privateFiles) { throw 'Unexpected ACL target.' }
    if (-not $entry.Acl.AreAccessRulesProtected) { throw 'ACL inheritance must be disabled.' }
    if ($entry.Acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $admins.Value) {
        throw 'Owner must be Administrators.'
    }
    $rules = @($entry.Acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 2) { throw 'Only two explicit access rules are allowed.' }
    $actualSids = @($rules | ForEach-Object { $_.IdentityReference.Value } | Sort-Object)
    if (($actualSids -join ',') -ne ((@($admins.Value, $system.Value) | Sort-Object) -join ',')) {
        throw 'Only SYSTEM and Administrators may have access.'
    }
    foreach ($rule in $rules) {
        if ($rule.IsInherited -or $rule.AccessControlType -ne 'Allow' -or
            $rule.FileSystemRights -ne [Security.AccessControl.FileSystemRights]::FullControl) {
            throw 'Expected explicit FullControl allow rules.'
        }
    }
}
[pscustomobject]@{
    powershell_scripts_parsed = $scriptFiles.Count
    powershell_documentation_blocks_parsed = $blockCount
    isolated_acl_targets_checked = $script:recordedAcls.Count
    live_acl_changes = $false
    live_server_changes = $false
} | ConvertTo-Json
