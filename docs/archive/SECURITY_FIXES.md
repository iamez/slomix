# COMPREHENSIVE SECURITY FIXES - MERGED AUDIT
## Combining Opus 4.1 + Sonnet 4.5 Findings

### CRITICAL FIXES TO APPLY

#### 1. Path Traversal - Map Upload/Delete (CRITICAL)
**Files:** server_control.py lines 479, 492, 577
**Status:** ❌ NOT FIXED (sanitize_filename exists but NOT USED)

**Current Code:**
```python
# Line 479 - map upload
temp_path = f"/tmp/{attachment.filename}"  # VULNERABLE!
# Line 492
remote_path = f"{self.maps_path}/{attachment.filename}"  # VULNERABLE!
# Line 577 - map delete
remote_path = f"{self.maps_path}/{map_name}"  # VULNERABLE!
```

**Fix Applied:**
```python
# Line 473 (add before line 479)
sanitized_name = sanitize_filename(attachment.filename)

# Line 479
temp_path = f"/tmp/{sanitized_name}"

# Line 492
remote_path = f"{self.maps_path}/{sanitized_name}"

# Line 572 (in map_delete, after .pk3 check)
map_name = sanitize_filename(map_name)

# Line 577
remote_path = f"{self.maps_path}/{map_name}"
```

#### 2. RCON Command Injection (HIGH)
**File:** server_control.py lines 620, 656, 679
**Status:** ❌ NOT FIXED

**Add sanitization function:**
```python
def sanitize_rcon_input(input_str: str) -> str:
    """Sanitize input for RCON commands - remove dangerous characters"""
    dangerous_chars = [';', '\n', '\r', '\x00', '`', '$', '|', '&']
    sanitized = input_str
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    return sanitized.strip()
```

**Apply to all RCON commands:**
```python
# Line 620 - rcon command
safe_command = sanitize_rcon_input(command)
response = rcon.send_command(safe_command)

# Line 656 - kick
safe_reason = sanitize_rcon_input(reason)
rcon.send_command(f'clientkick {player_id} "{safe_reason}"')

# Line 679 - say
safe_message = sanitize_rcon_input(message)
rcon.send_command(f'say "{safe_message}"')
```

#### 3. SSH Command Injection (HIGH)
**File:** server_control.py lines 220, 290-291, 496, 578
**Status:** ❌ PARTIALLY FIXED (needs shlex.quote)

**Add at top:**
```python
import shlex
```

**Fix command construction:**
```python
# Line 496 - chmod after upload
safe_path = shlex.quote(remote_path)
ssh.exec_command(f"chmod 644 {safe_path}")

# Line 578 - rm command
safe_path = shlex.quote(remote_path)
delete_command = f"rm -f {safe_path} && echo 'deleted' || echo 'failed'"
```

#### 4. Missing Imports (CRITICAL - WILL CRASH)
**File:** session_view_handlers.py
**Status:** ✅ FIXED

**Applied Fix:**
```python
import asyncio
from datetime import datetime
```

#### 5. PostgreSQL Configuration Default (CRITICAL)
**File:** bot/config.py line 37
**Status:** ❌ NOT CHECKED YET

**Opus's Fix:**
```python
# Change from:
self.database_type = self._get_config('DATABASE_TYPE', 'sqlite')

# To:
self.database_type = self._get_config('DATABASE_TYPE', 'postgresql')
```

#### 6. SSH Key Validation (HIGH - Prevents Crashes)
**File:** server_control.py __init__
**Status:** ❌ NOT FIXED

**Add validation:**
```python
def __init__(self, bot):
    # ... existing code ...
    if self.ssh_key_path and not os.path.exists(self.ssh_key_path):
        logger.warning(f"⚠️ SSH key not found: {self.ssh_key_path}")
        logger.warning("SSH features will be disabled")
        self.ssh_enabled = False
    else:
        self.ssh_enabled = True
```

#### 7. Connection Pool Size (MEDIUM)
**File:** bot/config.py
**Status:** ❌ NOT FIXED

**Opus's Recommendation:**
```python
# Change from:
self.postgres_min_pool = 5
self.postgres_max_pool = 20

# To:
self.postgres_min_pool = 10
self.postgres_max_pool = 30
```

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Critical Security (DO NOW)
- [ ] Fix path traversal in map upload (3 locations)
- [ ] Fix path traversal in map delete
- [ ] Add RCON input sanitization
- [ ] Add SSH command sanitization (shlex.quote)
- [ ] ✅ Fix missing imports in session_view_handlers.py

### Phase 2: Configuration (DO TODAY)
- [ ] Fix PostgreSQL default in config.py
- [ ] Add SSH key validation
- [ ] Increase connection pool size

### Phase 3: Testing (DO BEFORE DEPLOY)
- [ ] Test map upload with malicious filename
- [ ] Test map delete with path traversal attempt
- [ ] Test RCON with command injection attempt
- [ ] Test bot starts with missing SSH key
- [ ] Test PostgreSQL connection pool under load

---

## SEVERITY SUMMARY

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 5 | 1/5 Fixed |
| HIGH | 3 | 0/3 Fixed |
| MEDIUM | 2 | 0/2 Fixed |
| **TOTAL** | **10** | **1/10 Fixed** |

---

## NOTES
- sanitize_filename() function already exists but is NOT USED
- Most SQL queries are properly parameterized (✅ SAFE)
- No hardcoded credentials found (✅ GOOD)
- Audit logging exists and works well (✅ GOOD)
