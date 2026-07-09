# OPTIONAL: feed extra channels from a Windows PC's drives over SMB.
# Run elevated (right-click > Run as Administrator). Idempotent - safe to re-run.
#
# Creates a read-only local user 'etv' plus one read-only SMB share per entry
# in $shares. Your ErsatzTV host then CIFS-mounts them, e.g. in /etc/fstab:
#   //<windows-ip>/etv-videos  /media/pcq-videos  cifs  ro,_netdev,nofail,x-systemd.automount,vers=3.0,credentials=/root/.smb-creds  0 0
# with /root/.smb-creds containing:
#   username=etv
#   password=<the password below>
#
# RULES (learned the hard way, see docs/GOTCHAS.md):
# - Share a SUBFOLDER, never a drive root. Drive roots contain
#   'System Volume Information', which is ACL-locked and aborts
#   ErsatzTV's entire scan with UnauthorizedAccessException.
# - Media must be at least one folder deep inside the library path;
#   loose files in the path root are silently skipped by the scanner.
# - If the Windows PC reboots or re-letters drives, re-run this script,
#   then remount on the ErsatzTV host (mount -a) and rescan.

$ErrorActionPreference = 'Stop'
$pw = 'CHANGE-ME-Strong-Password!'   # <- change this, and put the same in /root/.smb-creds

# name -> path of every folder you want to feed to ErsatzTV
$shares = @(
  @{ Name = 'etv-videos';   Path = 'E:\Videos' }
  # @{ Name = 'etv-extended'; Path = 'D:\Extended Cuts' }
)

# 1. dedicated read-only local user
if (-not (Get-LocalUser -Name 'etv' -ErrorAction SilentlyContinue)) {
  New-LocalUser -Name 'etv' -Password (ConvertTo-SecureString $pw -AsPlainText -Force) `
    -PasswordNeverExpires -AccountNeverExpires -Description 'ErsatzTV read-only media share' | Out-Null
  Write-Host "created user etv"
} else { Write-Host "user etv already exists" }

foreach ($s in $shares) {
  if (-not (Test-Path $s.Path)) { Write-Warning "SKIP $($s.Name): path not found: $($s.Path)"; continue }

  # NTFS read for etv
  icacls $s.Path /grant 'etv:(OI)(CI)R' /T /C | Out-Null
  Write-Host "granted NTFS read on $($s.Path)"

  # drop a stale share (old drive letter) and (re)share at the current path
  $existing = Get-SmbShare -Name $s.Name -ErrorAction SilentlyContinue
  if ($existing -and $existing.Path -ne $s.Path) {
    Remove-SmbShare -Name $s.Name -Force
    $existing = $null
    Write-Host "removed stale share $($s.Name)"
  }
  if (-not $existing) {
    New-SmbShare -Name $s.Name -Path $s.Path -ReadAccess 'etv' | Out-Null
    Write-Host "shared $($s.Name) -> $($s.Path)"
  } else { Write-Host "share $($s.Name) already correct" }
}

# allow inbound SMB on the Private network profile
Enable-NetFirewallRule -DisplayGroup 'File and Printer Sharing' -ErrorAction SilentlyContinue

Get-SmbShare | Where-Object { $_.Name -like 'etv-*' } | Format-Table Name, Path -AutoSize
