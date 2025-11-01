# export_to_samba_with_auth.ps1
# Export the current project to a Samba share using credentials (prompts for username/password),
# copies the installer script to the share, and optionally copies SSH private keys (with confirmation).
# This version maps the share using New-PSDrive (Get-Credential) to ensure authenticated access.
#
# Usage:
#   1. From the repo on your Windows PC run:
#        cd G:\VisualStudio\Python\stats\tools
#        .\export_to_samba_with_auth.ps1
#
# The script will prompt for credentials and the share root to use (defaults provided).

# --------- CONFIG (change defaults if you want) ----------
$defaultShare = "\\192.168.64.116\share"
$shareSubDir = "SCRIPTS\vscode\stats"
$driveName = "Z"
$robocopyOptions = @("/E","/COPY:DAT","/R:3","/W:5","/MT:8","/ETA")
$keyNamePatterns = @("id_rsa","id_ed25519","puran_id_rsa","puran_id_ed25519","deploy_key*")
# --------------------------------------------------------

function Write-Info($s) { Write-Host $s -ForegroundColor Cyan }
function Write-Warn($s) { Write-Host $s -ForegroundColor Yellow }
function Write-Err($s) { Write-Host $s -ForegroundColor Red }

# locate project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Get-Item (Join-Path $scriptDir "..") ).FullName
Write-Info "Project root detected: $projectRoot"

# Prompt for share root (default provided)
$shareRoot = Read-Host "Samba share root (UNC). Press Enter to use default: $defaultShare"
if ([string]::IsNullOrWhiteSpace($shareRoot)) { $shareRoot = $defaultShare }

# Prompt for credential
Write-Info "You will be prompted for credentials to access the share. Use format DOMAIN\\user or user as appropriate."
$cred = Get-Credential

# Map the share using New-PSDrive
try {
    # remove existing drive with same name if present
    if (Get-PSDrive -Name $driveName -ErrorAction SilentlyContinue) {
        Remove-PSDrive -Name $driveName -Force -ErrorAction SilentlyContinue
    }
    New-PSDrive -Name $driveName -PSProvider FileSystem -Root $shareRoot -Credential $cred -Persist | Out-Null
    Write-Info ("Mapped {0} to {1}:\\" -f $shareRoot, $driveName)
} catch {
    Write-Err ("Failed to map drive to {0}: {1}" -f $shareRoot, $_)
    throw
}

# Build destination path on mapped drive
$destOnDrive = Join-Path "$($driveName):\" $shareSubDir
Write-Info "Target on share (mapped): $destOnDrive"

# Ensure destination exists
try {
    New-Item -ItemType Directory -Path $destOnDrive -Force | Out-Null
} catch {
    Write-Err ("Failed to create destination {0}: {1}" -f $destOnDrive, $_)
    # cleanup drive mapping
    Remove-PSDrive -Name $driveName -Force -ErrorAction SilentlyContinue
    throw
}

# Run robocopy
Write-Info "Starting robocopy: $projectRoot -> $destOnDrive"
$robArgs = @($projectRoot, $destOnDrive) + $robocopyOptions
robocopy @robArgs
if ($LASTEXITCODE -ge 8) {
    Write-Err "robocopy returned exit code $LASTEXITCODE which indicates a failure. Check connectivity and permissions."
} else {
    Write-Info "Project copied to share (robocopy exit code $LASTEXITCODE)."
}

# Copy installer script
$installerLocal = Join-Path $projectRoot "tools\copy_workspace_and_ssh.ps1"
$installerDestParent = Join-Path $destOnDrive "tools"
$installerDest = Join-Path $installerDestParent "copy_workspace_and_ssh.ps1"
if (-not (Test-Path $installerLocal)) {
    Write-Warn "Local installer script not found at $installerLocal. Skipping installer copy."
} else {
    New-Item -ItemType Directory -Path $installerDestParent -Force | Out-Null
    Copy-Item -Path $installerLocal -Destination $installerDest -Force
    Write-Info "Installer script copied to $installerDest"
}

# Optionally copy SSH keys (explicit confirmation)
$copyKeysAnswer = Read-Host "Do you want to copy private SSH key files from this machine to the share's deploy_keys folder? (y/N)"
if ($copyKeysAnswer -match '^[Yy]') {
    Write-Warn "Copying private keys to the share is a security risk. Proceed only if you understand this."
    $sshLocalDir = Join-Path $env:USERPROFILE ".ssh"
    if (-not (Test-Path $sshLocalDir)) {
        Write-Err "Local .ssh folder not found at $sshLocalDir. Aborting key copy."
    } else {
        $deployDir = Join-Path $destOnDrive "deploy_keys"
        New-Item -ItemType Directory -Path $deployDir -Force | Out-Null
        $found = @()
        foreach ($pat in $keyNamePatterns) {
            $foundMatches = Get-ChildItem -Path $sshLocalDir -Filter $pat -File -ErrorAction SilentlyContinue
            foreach ($m in $foundMatches) { $found += $m }
        }
        if ($found.Count -eq 0) {
            Write-Warn "No candidate key files found by name. Listing non-.pub files in $sshLocalDir."
            $allPrivateCandidates = Get-ChildItem -Path $sshLocalDir -File | Where-Object { $_.Extension -ne '.pub' }
            if ($allPrivateCandidates.Count -gt 0) {
                $confirm = Read-Host "Copy all non-.pub files from $sshLocalDir to the share? (y/N)"
                if ($confirm -match '^[Yy]') { $found = $allPrivateCandidates }
            }
        }
        foreach ($f in $found) {
            $target = Join-Path $deployDir $f.Name
            Copy-Item -Path $f.FullName -Destination $target -Force
            Write-Info "Copied key: $f.Name -> $target"
            try {
                icacls $target /inheritance:r | Out-Null
                icacls $target /grant:r "$($env:USERNAME):(R)" | Out-Null
                Write-Info "Applied ACLs restricting access on the copy."
            } catch {
                Write-Warn "Failed to set ACLs on $target."
            }
        }
        Write-Warn "Keys copied to $deployDir. Remember to delete them from the share after use."
    }
} else {
    Write-Info "Skipping private SSH key copy (recommended)."
}

Write-Info "Operation complete. You can unmap the drive if you want: Remove-PSDrive -Name $driveName -Force"
