# PostgreSQL Remote Access Instructions

To allow the website backend (running on Windows) to connect to the bot's database (running on Linux), please make the following changes on the Linux server.

### 1. Edit `postgresql.conf`
Find the configuration file (usually in `/etc/postgresql/14/main/postgresql.conf` or similar version).

**Change:**
```ini
#listen_addresses = 'localhost'
```
**To:**
```ini
listen_addresses = '*'
```

### 2. Edit `pg_hba.conf`
Find the HBA file (usually in the same directory as `postgresql.conf`).

**Add this line to the end of the file:**
```ini
# Allow website backend from Windows machine
host    etlegacy    etlegacy_user    192.168.64.131/32    md5
```
*(This allows ONLY your Windows machine IP `192.168.64.131` to connect)*

### 3. Restart PostgreSQL
Apply the changes by restarting the service:
```bash
sudo systemctl restart postgresql
```

### 4. Verify
After restarting, I will run the connection test script again.
