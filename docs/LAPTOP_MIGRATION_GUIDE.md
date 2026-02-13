# 🚀 Slomix Dev Migration Guide (PC -> Laptop)

**Current Status**: ✅ Backend is connected to Production PostgreSQL (`192.168.64.116`).

## 🛑 The Blocker: IP Whitelisting

The PostgreSQL server on the Linux VM is configured to **only allow specific IPs**.
Your current PC (`192.168.64.131`) is whitelisted.
**Your Laptop will have a different IP and will be blocked by default.**

---

## 🛠️ Steps to Resume on Laptop

### 1. Find Laptop's IP

Open a terminal on your laptop and run:

```powershell
ipconfig
# Verify you are in the 192.168.64.x range
```text

### 2. Server Configuration (ALREADY DONE ✅)

You have already whitelisted the entire subnet (`192.168.64.0/24`) on the Linux server.
**No further action needed on the server.**

### 3. Verify Project Config

Ensure your project files on the laptop have the correct `.env` settings:

**File**: `z:\slomix_discord\.env`

```ini
DATABASE_TYPE=postgresql
POSTGRES_HOST=192.168.64.116
POSTGRES_PORT=5432
POSTGRES_USER=etlegacy_user
POSTGRES_PASSWORD=REDACTED_DB_PASSWORD
POSTGRES_DATABASE=etlegacy
```text

### 4. Start the Backend

```powershell
# In z:\slomix_discord
python -m uvicorn website.backend.main:app --reload --host 0.0.0.0 --port 8000
```sql

---

## 🌍 Offline Mode (New!)

If you are taking the laptop away from the network, use the new migration scripts to set up a fully local environment.

### 1. Migrate Files

**Option A: Manual Copy (Easiest if scripts fail)**

1. Copy the entire `slomix_discord` folder from `Z:\` to `C:\Users\seareal\Documents\`.
2. **Important**: Delete the `.venv` folder in the new copy (it contains links to the old location).
3. Open a terminal in `C:\Users\seareal\Documents\slomix_discord` and run:

    ```powershell
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    ```sql

**Option B: Use Script**
Run this from the Z: drive:

```powershell
cd Z:\slomix_discord
PowerShell -ExecutionPolicy Bypass -File .\migrate_to_laptop.ps1
```text

### 2. Setup Local Database

Once the files are on your C: drive, go there and run the DB setup:

```powershell
cd C:\Users\seareal\Documents\slomix_discord
PowerShell -ExecutionPolicy Bypass -File .\setup_local_db.ps1
```python

* **With Docker**: It will spin up a Postgres container and import the latest backup.
* **Without Docker**: It will help you configure SQLite or a manual Postgres connection.

### 3. Start Local Server

```powershell
cd C:\Users\seareal\Documents\slomix_discord
.venv\Scripts\activate
python -m uvicorn website.backend.main:app --reload
```
