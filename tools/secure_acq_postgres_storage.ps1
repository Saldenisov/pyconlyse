$ErrorActionPreference = 'Stop'
$taskPgRoot = (Resolve-Path -LiteralPath 'F:\ELYSE_PostgreSQL').Path
if ($taskPgRoot -ne 'F:\ELYSE_PostgreSQL') { throw 'Unexpected PostgreSQL storage root' }
$taskPgIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$taskPgPrior = Get-Acl -LiteralPath $taskPgRoot
$taskPgBackup = Join-Path $taskPgRoot 'secrets\storage_acl_before.sddl'
if (-not (Test-Path -LiteralPath $taskPgBackup)) {
    $taskPgPrior.Sddl | Set-Content -LiteralPath $taskPgBackup -Encoding ASCII
}
$taskPgAcl = New-Object System.Security.AccessControl.DirectorySecurity
$taskPgAcl.SetAccessRuleProtection($true, $false)
$taskPgInheritance = [System.Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
foreach ($taskPgSid in @($taskPgIdentity.User, [System.Security.Principal.SecurityIdentifier]'S-1-5-18')) {
    $taskPgRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $taskPgSid, 'FullControl', $taskPgInheritance, 'None', 'Allow')
    $taskPgAcl.AddAccessRule($taskPgRule)
}
Set-Acl -LiteralPath $taskPgRoot -AclObject $taskPgAcl
Get-Acl -LiteralPath $taskPgRoot | Select-Object Path, AccessToString
