# setup_env.ps1
# Creates a .venv in the project root and installs requirements.txt
# Usage: Open PowerShell, cd to project root, then run:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force; .\setup_env.ps1

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location -Path $projectRoot

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 --version
    py -3 -m venv .venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python --version
    python -m venv .venv
} else {
    Write-Host "No Python launcher found. Please install Python 3 and ensure 'py' or 'python' is on PATH."
    Write-Host "Download from https://www.python.org/downloads/ and enable 'Add Python to PATH' during install."
    exit 1
}

# Upgrade pip and install requirements without requiring activation
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $venvPython -m pip install -U pip
& $venvPython -m pip install -r requirements.txt

Write-Host "Virtual environment created and packages installed (if Python was available)."
