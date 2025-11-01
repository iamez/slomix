# export_to_samba.ps1
# Copy the current project workspace to a Samba share so you can pull it from your laptop.
# Also copies the installer script (copy_workspace_and_ssh.ps1) to the share so the laptop can run it.
#
# IMPORTANT: copying private SSH keys to a network share is a security risk. The script will ask for
# interactive confirmation before copying any private keys.
#
# Usage:
#  1. Edit CONFIG below if you want to change defaults.
#  2. Run from this repo on your Windows PC:
#       cd G:\VisualStudio\Python\stats\tools
#       .\export_to_samba.ps1
#
# The script will:
#  - copy the project folder (repo root) into a subfolder on the share (default: <samba>\stats)
#  - copy the helper installer script tools\copy_workspace_and_ssh.ps1 to the share under tools\
#  - optionally copy SSH private keys into <samba>\deploy_keys (only with explicit confirmation)
#
# Robocopy is used for robust copying.

# --------- CONFIG ----------
# UNC to target samba share (edit if needed)
$samba = "\\192.168.64.116\share\SCRIPTS\vscode"

# Destination folder name inside the share
$shareSubDir = "stats"

# Robocopy options for copying the project
$robocopyOptions = @("/E","/COPY:DAT","/R:3","/W:5","/MT:8","/ETA")

# Patterns to pick up for private key copying (if confirmed)
$keyNamePatterns = @("id_rsa","id_ed25519","puran_id_rsa","puran_id_ed25519","deploy_key*")
# ---------------------------

function Write-Info($s) { Write-Host $s -ForegroundColor Cyan }
function Write-Warn($s) { Write-Host $s -ForegroundColor Yellow }
function Write-Err($s) { Write-Host $s -ForegroundColor Red }

# Resolve project root (parent of this tools folder)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Get-Item (Join-Path $scriptDir "..") ).FullName
Write-Info "Project root detected: $projectRoot"

# Build destination path on share
$destOnShare = Join-Path $samba $shareSubDir
Write-Info "Target on share: $destOnShare"

# Ensure the share root exists by creating the directory locally (NTFS create over UNC will create it on the share)
try {
    New-Item -ItemType Directory -Path $destOnShare -Force | Out-Null
} catch {
    Write-Err "Failed to create destination on share. Verify the UNC path and network connectivity: $samba"
    throw
}

# Copy the project using robocopy
Write-Info "Starting robocopy: $projectRoot -> $destOnShare"
$robArgs = @($projectRoot, $destOnShare) + $robocopyOptions
robocopy @robArgs
if ($LASTEXITCODE -ge 8) {
    Write-Warn "robocopy returned exit code $LASTEXITCODE which indicates a failure. Check connectivity and permissions."
} else {
    Write-Info "Project copied to share (robocopy exit code $LASTEXITCODE)."
}

# Copy the installer script to the share under tools\ so the laptop can use it
$installerLocal = Join-Path $projectRoot "tools\copy_workspace_and_ssh.ps1"
$installerDestParent = Join-Path $destOnShare "tools"
$installerDest = Join-Path $installerDestParent "copy_workspace_and_ssh.ps1"

if (-not (Test-Path $installerLocal)) {
    Write-Warn "Local installer script not found at $installerLocal. Ensure copy_workspace_and_ssh.ps1 is present in tools/."
} else {
    New-Item -ItemType Directory -Path $installerDestParent -Force | Out-Null
    Copy-Item -Path $installerLocal -Destination $installerDest -Force
    Write-Info "Installer script copied to $installerDest"
}

# Ask user whether to copy private SSH keys (dangerous). Default: no.
$copyKeysAnswer = Read-Host "Do you want to copy private SSH key files from this machine to the share? (y/N)"
if ($copyKeysAnswer -match '^[Yy]') {
    Write-Warn "You chose to copy private SSH keys. This is a security risk. The keys will be copied to $destOnShare\deploy_keys"

    $sshLocalDir = Join-Path $env:USERPROFILE ".ssh"
    if (-not (Test-Path $sshLocalDir)) {
        Write-Err "No local .ssh folder found at $sshLocalDir. Aborting key copy."
    } else {
        $deployDir = Join-Path $destOnShare "deploy_keys"
        New-Item -ItemType Directory -Path $deployDir -Force | Out-Null

        $found = @()
        foreach ($pat in $keyNamePatterns) {
            $foundMatches = Get-ChildItem -Path $sshLocalDir -Filter $pat -File -ErrorAction SilentlyContinue
            foreach ($m in $foundMatches) { $found += $m }
        }

        if ($found.Count -eq 0) {
            Write-Warn "No key files found in $sshLocalDir matching patterns."
            # Offer to copy all non-public files (conservative)
            $allPrivateCandidates = Get-ChildItem -Path $sshLocalDir -File | Where-Object { $_.Extension -ne '.pub' }
            if ($allPrivateCandidates.Count -gt 0) {
                $confirm = Read-Host "Copy all non-.pub files from $sshLocalDir to the share? (y/N)"
                if ($confirm -match '^[Yy]') { $found = $allPrivateCandidates }
            }
        }

        if ($found.Count -gt 0) {
            foreach ($f in $found) {
                $target = Join-Path $deployDir $f.Name
                Copy-Item -Path $f.FullName -Destination $target -Force
                Write-Info "Copied key: $f.Name -> $target"
                try {
                    icacls $target /inheritance:r | Out-Null
                    icacls $target /grant:r "$($env:USERNAME):(R)" | Out-Null
                    Write-Info "Applied ACLs restricting access on the copy (may not map across machines)."
                } catch {
                    Write-Warn "Failed to set ACLs on $target."
                }
            }
            Write-Warn "Keys copied to $deployDir. Remove them from the share when not needed."
        } else {
            Write-Warn "No key files copied."
        }
    }
} else {
    Write-Info "Skipping private SSH key copy (recommended)."
}

Write-Info "Export complete. On the laptop, run the 'copy_workspace_and_ssh.ps1' installer script from the share to pull the workspace and setup the env."
