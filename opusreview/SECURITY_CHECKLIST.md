# SLOMIX BOT - SECURITY FIX QUICK REFERENCE

## 🚨 IMMEDIATE ACTIONS (Do These First!)

### 1. Backup Everything
```bash
tar -czf slomix_backup_$(date +%Y%m%d).tar.gz bot/
```

### 2. Install Security Dependencies
```bash
pip install -r requirements_security.txt
```

### 3. Get SSH Server Fingerprint
```bash
ssh-keyscan -H puran.hehe.si >> ~/.ssh/slomix_known_hosts
```

---

## 📁 FILES TO CREATE

Create these new files in your bot directory:

1. `bot/core/secure_ssh.py` - SSH with host verification
2. `bot/core/secure_database.py` - SQL injection prevention
3. `bot/core/secure_config.py` - Encrypted credential storage
4. `bot/core/validators.py` - Input validation
5. `bot/core/rate_limiter.py` - Rate limiting
6. `bot/core/audit_logger.py` - Audit logging
7. `setup_secrets.py` - Interactive secret configuration
8. `test_security.py` - Security test suite

---

## 🔧 FILES TO MODIFY

### CRITICAL Changes (Fix Today)

#### `bot/automation/ssh_handler.py`
- Line ~87: Replace `paramiko.AutoAddPolicy()` with `secure_ssh_manager.get_ssh_client()`
- Line ~125: Replace `paramiko.AutoAddPolicy()` with `secure_ssh_manager.get_ssh_client()`

#### `bot/services/automation/ssh_monitor.py`
- Line ~285: Replace `paramiko.AutoAddPolicy()` with `secure_ssh_manager.get_ssh_client()`
- Line ~325: Replace `paramiko.AutoAddPolicy()` with `secure_ssh_manager.get_ssh_client()`

#### `bot/cogs/server_control.py`
- Line ~144: Replace `paramiko.AutoAddPolicy()` with secure version
- Add `shlex.quote()` to all command parameters
- Update all `exec_command()` calls to use parameterized commands

#### `bot/ultimate_bot.py`
- Line ~1070: Replace `paramiko.AutoAddPolicy()` with secure version
- Update all SSH operations to use `secure_ssh_manager`

#### ALL Database Queries
- Replace ALL f-strings in SQL queries with parameterized queries
- Use `$1, $2, $3` placeholders for PostgreSQL
- Never concatenate user input into queries

---

## ✅ TESTING CHECKLIST

After making changes, test each fix:

### Test SSH Security
```bash
# Should fail with unknown host
python -c "from bot.core.secure_ssh import secure_ssh_manager; secure_ssh_manager.get_ssh_client({'host': 'unknown.com', 'port': 22, 'user': 'test', 'key_path': '~/.ssh/id_rsa'})"
```

### Test SQL Injection Prevention
```python
# These should all return empty/safe results
test_inputs = ["'; DROP TABLE players; --", "' OR '1'='1", "admin'--"]
for inp in test_inputs:
    await secure_db.search_players_secure(inp)
```

### Test Command Injection
```python
# These should be safely escaped
dangerous_inputs = ["; rm -rf /", "| cat /etc/passwd", "`whoami`"]
for inp in dangerous_inputs:
    safe = shlex.quote(inp)
    print(f"Input: {inp} -> Safe: {safe}")
```

### Run Full Security Test
```bash
python test_security.py
```

---

## 📊 PROGRESS TRACKER

Copy this to track your progress:

- [ ] Created backup
- [ ] Installed dependencies
- [ ] Created secure_ssh.py
- [ ] Created secure_database.py  
- [ ] Created secure_config.py
- [ ] Created validators.py
- [ ] Created rate_limiter.py
- [ ] Created audit_logger.py
- [ ] Fixed SSH in ssh_handler.py
- [ ] Fixed SSH in ssh_monitor.py
- [ ] Fixed SSH in server_control.py
- [ ] Fixed SSH in ultimate_bot.py
- [ ] Fixed SQL queries in link_cog.py
- [ ] Fixed SQL queries in stats_cog.py
- [ ] Fixed SQL queries in admin_cog.py
- [ ] Added rate limiting to commands
- [ ] Set up secure credentials
- [ ] Tested SSH connections
- [ ] Tested SQL injection prevention
- [ ] Tested command injection prevention
- [ ] Ran test_security.py
- [ ] All tests passing

---

## 🆘 TROUBLESHOOTING

### SSH Connection Fails
1. Check if SSH key exists: `ls -la ~/.ssh/id_rsa`
2. Verify server fingerprint: `ssh-keyscan puran.hehe.si`
3. Test manual connection: `ssh user@puran.hehe.si`

### Database Queries Fail
1. Check parameter count matches placeholders
2. Ensure using `$1, $2` for PostgreSQL (not `?`)
3. Verify query syntax with: `EXPLAIN (ANALYZE, BUFFERS) your_query;`

### Import Errors
1. Ensure all new files are in correct directories
2. Check Python path: `python -c "import sys; print(sys.path)"`
3. Verify imports: `python -c "from bot.core.secure_ssh import secure_ssh_manager"`

---

## 🎯 FINAL VERIFICATION

Before deploying to production:

1. **No AutoAddPolicy() anywhere**
   ```bash
   grep -r "AutoAddPolicy()" bot/
   ```

2. **No f-strings in SQL**
   ```bash
   grep -r 'f".*SELECT\|INSERT\|UPDATE\|DELETE' bot/
   ```

3. **All secrets encrypted**
   ```bash
   grep -r 'password\s*=\s*["'\'']' bot/ | grep -v getenv
   ```

4. **Security test passes**
   ```bash
   python test_security.py
   ```

---

## 📞 SUPPORT

If you get stuck:
1. Check the full guide: `SLOMIX_SECURITY_FIXES.md`
2. Review test output: `python test_security.py`
3. Check logs: `tail -f logs/bot.log`
4. Verify dependencies: `pip list | grep -E "paramiko|cryptography|asyncpg"`

---

Good luck! You've got this! 🚀
