$cwd = "G:\VisualStudio\Python\stats"
$publish = Join-Path $cwd "publish_temp"
if (Test-Path $publish) { Remove-Item -Recurse -Force $publish }
New-Item -ItemType Directory -Path $publish | Out-Null

# Copy files excluding common unwanted dirs and large DB files
robocopy $cwd $publish /E /XD ".git" "temp" "__pycache__" ".venv" "venv" "env" /XF "*.db" "*.sqlite" "*.sqlite3" "*.bak" "*.zip" "*.tar" "*.gz" | Out-Null

# Remove any remaining DB files just in case
Get-ChildItem -Path $publish -Recurse -Include *.db,*.sqlite,*.sqlite3 -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

Set-Location $publish

# Create .gitignore
$gitignore = @"
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
venv/
.env
.env.*
# DBs and backups
*.db
*.sqlite
*.sqlite3
*.bak
# temp files
temp/
dist/
build/
"@
$gitignore | Out-File -Encoding utf8 .gitignore

# Create README
$readme = @"
slomix-stats ??? Cleaned ET:Legacy stats repo
This repository was created from the local workspace snapshot and excludes DB backups and large temp files.
"@
$readme | Out-File -Encoding utf8 README.md

# Initialize git and push
if (-not (Test-Path ".git")) {
    git init
}

git add .

# Avoid committing if nothing changed
$changes = git status --porcelain
if (-not [string]::IsNullOrEmpty($changes)) {
    git commit -m "Initial import ??? cleaned snapshot for slomix-stats"
} else {
    Write-Output "No changes to commit."
}

git branch -M main

# Set remote (replace if exists)
if ((git remote) -contains "origin") {
    git remote remove origin
}

git remote add origin https://github.com/iamez/slomix-stats.git

# Push and capture output
git push -u origin main

Write-Output "Script completed."
