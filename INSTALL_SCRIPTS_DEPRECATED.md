# Installation Scripts - Deprecation Notice

## ⚠️ These Scripts Are Deprecated

The following installation scripts have been **consolidated** into a single unified installer:

### Deprecated Scripts (Do Not Use)
- ❌ `setup_linux_bot.sh` (355 lines) - Replaced by `install.sh --full`
- ❌ `vps_install.sh` (106 lines) - Replaced by `install.sh --vps --auto`
- ❌ `vps_setup.sh` (252 lines) - Replaced by `install.sh --vps --interactive`
- ❌ `setup_linux_env.sh` (96 lines) - Replaced by `install.sh --env-only`

## ✅ Use This Instead

### Unified Installation Script: `install.sh`

**One script, multiple modes:**

```bash
# Full automated installation (same as old setup_linux_bot.sh)
sudo ./install.sh --full --auto

# VPS auto setup (same as old vps_install.sh)
sudo ./install.sh --vps --auto

# VPS interactive setup (same as old vps_setup.sh)
sudo ./install.sh --vps --interactive

# Environment only (same as old setup_linux_env.sh)
./install.sh --env-only
```

## Why Consolidate?

**Before:** 4 different scripts, ~800 lines total, overlapping functionality, confusing to users

**After:** 1 unified script, ~850 lines, all features preserved, clearer usage

### Benefits of Unified Script

1. **Single Source of Truth** - One script to maintain and update
2. **Consistent Behavior** - Same logic for all installation scenarios
3. **Flexible Options** - Mix and match features with flags
4. **Better Documentation** - Built-in `--help` with examples
5. **No Duplication** - Shared functions, no copy/paste code

## Migration Guide

| Old Command | New Command |
|-------------|-------------|
| `sudo ./setup_linux_bot.sh` | `sudo ./install.sh --full --interactive` |
| `sudo ./vps_install.sh` | `sudo ./install.sh --vps --auto` |
| `sudo ./vps_setup.sh` | `sudo ./install.sh --vps --interactive` |
| `./setup_linux_env.sh` | `./install.sh --env-only` |

## Advanced Usage

The unified script supports many more options:

```bash
# Skip PostgreSQL but install everything else
sudo ./install.sh --full --skip-postgresql

# Skip systemd service creation
sudo ./install.sh --vps --skip-systemd

# Custom installation directory
sudo ./install.sh --full --deploy-dir /opt/mybot

# Skip initial database import
sudo ./install.sh --vps --skip-import

# View all options
./install.sh --help
```

## Timeline

- **November 2025** - Unified `install.sh` created, old scripts deprecated
- **Current** - Both old and new scripts coexist (transition period)
- **Future** - Old scripts will be removed in a future release

## Questions?

Run `./install.sh --help` for complete documentation and examples.
