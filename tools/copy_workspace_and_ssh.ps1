# copy_workspace_and_ssh.ps1
# Robust script to copy a VS Code workspace from a Samba share to this laptop,
# copy likely SSH private keys into %USERPROFILE%\.ssh and harden ACLs,
# create a Python virtualenv and install requirements if present, and open VS Code.
#
# Edit the variables in the CONFIG section below before running.

<#
Usage:
  1. Edit the CONFIG section at the top if needed (UNC share, destination).
  2. Open PowerShell (normal user) and run:
       cd <where-you-saved-this-script>
       .\copy_workspace_and_ssh.ps1

Notes:
 - If the Samba share requires credentials, map it first with `net use` or set $useDriveLetter = $true.
 - The script attempts to discover likely private keys; if it doesn't find your key, specify the exact filename in $keyNamePatterns.
 - For security, prefer creating a new SSH keypair on the laptop and adding the public key to the remote.
#>

# --------- CONFIG ----------
# UNC to the samba share you gave earlier. Adjust if needed.
$samba = "\\192.168.64.116\share\SCRIPTS\vscode"

# Destination on the laptop: default is Projects\stats inside the current user's profile
$dest = Join-Path $env:USERPROFILE "Projects\stats"

# If your share needs mapping with credentials, set to $true and change $driveLetter
$useDriveLetter = $false
$driveLetter = "Z:"

# File name patterns to search for private keys on the share (can add exact filenames)
$keyNamePatterns = @("id_rsa","id_ed25519","puran_id_rsa","puran_id_ed25519","*puran*","deploy_key*")

# Whether to search recursively under the samba share for candidate keys (can be slow)
$searchRecursively = $true

# Robocopy options (defaults used by script)
$robocopyOptions = @("/E","/COPY:DAT","/R:3","/W:5","/MT:8","/ETA")
# ---------------------------

function Write-Info($s) { Write-Host $s -ForegroundColor Cyan }
function Write-Warn($s) { Write-Host $s -ForegroundColor Yellow }
function Write-Err($s) { Write-Host $s -ForegroundColor Red }

# Create destination folder
Write-Info "Destination: $dest"
New-Item -ItemType Directory -Path $dest -Force | Out-Null

# Optionally map drive letter
if ($useDriveLetter) {
    Write-Info "Mapping $samba to $driveLetter (interactive prompt may appear)"
    net use $driveLetter $samba | Out-Null
    $src = "$driveLetter\"
} else {
    $src = $samba
}

# Copy workspace with robocopy
Write-Info "Starting robocopy from $src to $dest ..."
$robocopyArgs = @($src, $dest) + $robocopyOptions
robocopy @robocopyArgs

# Discover candidate SSH private keys on the share
$foundKeys = @()
$commonPaths = @(
    ".ssh",
    "deploy_keys",
    "keys",
    "config",
    ""
)

foreach ($base in $commonPaths) {
    foreach ($pat in $keyNamePatterns) {
        $candidate = Join-Path $samba $base
        try {
            if ($searchRecursively) {
                $foundMatches = Get-ChildItem -Path $candidate -Recurse -Filter $pat -ErrorAction SilentlyContinue | Where-Object { -not $_.PSIsContainer }
            } else {
                $foundMatches = Get-ChildItem -Path $candidate -Filter $pat -ErrorAction SilentlyContinue | Where-Object { -not $_.PSIsContainer }
            }
            foreach ($m in $foundMatches) {
                if ($m.Length -gt 0 -and -not ($foundKeys -contains $m.FullName)) {
                    $foundKeys += $m.FullName
                }
            }
        } catch {
            # ignore missing folders or access errors
        }
    }
}

# If none found by name, do a light content scan for PEM-like headers (small files only)
if ($foundKeys.Count -eq 0) {
    Write-Info "No candidate key files found by name; doing a light content scan..."
    try {
        $textMatches = Get-ChildItem -Path $samba -Recurse -ErrorAction SilentlyContinue -File |
            Where-Object { $_.Length -lt 20000 } |
            Where-Object {
                try {
                    Select-String -Path $_.FullName -Pattern "-----BEGIN (OPENSSH|RSA|PRIVATE) KEY-----" -SimpleMatch -Quiet -ErrorAction SilentlyContinue
                } catch { $false }
            }
        foreach ($tm in $textMatches) { $foundKeys += $tm.FullName }
    } catch {
        Write-Warn "Content scan failed or timed out: $_"
    }
}

# Copy found keys to user's .ssh
$sshDir = Join-Path $env:USERPROFILE ".ssh"
if ($foundKeys.Count -eq 0) {
    Write-Warn "No private key files were discovered automatically. If you know the key path, run the script again after editing `\$keyNamePatterns` or copy the key manually."
} else {
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
    Write-Info "Found $($foundKeys.Count) candidate key file(s). Copying to $sshDir ..."
    foreach ($k in $foundKeys) {
        $baseName = [IO.Path]::GetFileName($k)
        $destKey = Join-Path $sshDir $baseName

        Write-Info "Copying: $k -> $destKey"
        Copy-Item -Path $k -Destination $destKey -Force

        # Harden ACL: remove inheritance and grant only the current user full access
        Write-Info "Applying restrictive ACL to $destKey"
        try {
            icacls $destKey /inheritance:r | Out-Null
            icacls $destKey /grant:r "$($env:USERNAME):(F)" | Out-Null
            icacls $destKey /remove "Users" "Authenticated Users" "Everyone" | Out-Null
        } catch {
            Write-Warn "Failed to set ACLs on $destKey (you may need additional privileges)."
        }
    }
}

# Copy SSH config if present (will not overwrite existing config)
$sshConfigSrc = Join-Path $samba ".ssh\config"
$sshConfigDst = Join-Path $sshDir "config"
if (Test-Path $sshConfigSrc -PathType Leaf -ErrorAction SilentlyContinue -and -not (Test-Path $sshConfigDst)) {
    Write-Info "Copying SSH config from share to $sshConfigDst"
    Copy-Item -Path $sshConfigSrc -Destination $sshConfigDst -Force
    icacls $sshConfigDst /inheritance:r | Out-Null
    icacls $sshConfigDst /grant:r "$($env:USERNAME):(R)" | Out-Null
}

# Create virtualenv if Python is present
$pythonCmd = (Get-Command python -ErrorAction SilentlyContinue).Path
if (-not $pythonCmd) {
    Write-Warn "Python not found in PATH. Skipping virtualenv creation. Install Python and re-run if desired."
} else {
    Write-Info "Python found: $pythonCmd"
    Push-Location $dest
    if (-not (Test-Path ".\.venv")) {
        Write-Info "Creating virtual environment at $dest\.venv"
        & $pythonCmd -m venv .\.venv
    } else {
        Write-Info ".venv already exists at $dest\.venv"
    }

    $venvPy = Join-Path $dest ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
        Write-Info "Upgrading pip and installing requirements (if requirements.txt exists)"
        & $venvPy -m pip install --upgrade pip
        if (Test-Path ".\requirements.txt") {
            & $venvPy -m pip install -r .\requirements.txt
        } else {
            Write-Info "No requirements.txt found; skipping pip install."
        }
    } else {
        Write-Warn "Virtualenv python not found at $venvPy"
    }
    Pop-Location
}

# Open in VS Code if available
if (Get-Command code -ErrorAction SilentlyContinue) {
    Write-Info "Opening $dest in VS Code..."
    code $dest
} else {
    Write-Info "'code' not found on PATH. Open VS Code and select File -> Open Folder -> $dest"
}

Write-Info "Script complete. Check $dest and $sshDir. Test SSH with: ssh -i <path-to-key> username@puran.hehe.si"
