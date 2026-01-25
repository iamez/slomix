# ET:Legacy Server Optimization Session
**Date:** 2026-01-25
**Server:** puran.hehe.si (LXC container on Debian 11)

## Summary

Optimized the ET:Legacy game server for better performance and reduced player lag. Server is hosted in Slovenia with mostly local players (LAN-like environment).

## Server Environment

| Spec | Value |
|------|-------|
| CPU | Intel Xeon E5-2450L @ 1.80GHz (8 cores) |
| RAM | 94GB (server uses ~170MB) |
| OS | Debian 11 (kernel 5.10) |
| Virtualization | LXC container |
| Game Server | ET:Legacy v2.83.1 |

## Changes Made

### 1. UDP Buffer Optimization (Active Immediately)

**File created:** `/etc/sysctl.d/99-etlegacy.conf`

```bash
# ET:Legacy Game Server Network Optimizations
net.ipv4.udp_rmem_min = 16384    # Was: 4096
net.ipv4.udp_wmem_min = 16384    # Was: 4096
```

**Note:** Other network sysctls (rmem_max, wmem_max, etc.) failed because LXC containers inherit these from the host.

**Impact:** Reduces UDP packet drops under load.

### 2. CPU Affinity (Active After Restart)

**File modified:** `/home/et/etlegacy-v2.83.1-x86_64/etdaemon.sh`

Changed startup command from:
```bash
screen -dmS vektor $GAME_DIR/etlded.x86_64 +exec vektor.cfg
```

To:
```bash
screen -dmS vektor taskset -c 0,1 $GAME_DIR/etlded.x86_64 +exec vektor.cfg
```

**Impact:** Pins game server to CPU cores 0 and 1, improving cache locality and reducing context switch overhead.

### 3. Not Implemented

| Optimization | Reason |
|--------------|--------|
| nice -5 priority | Requires root/sudo, minor benefit |
| sv_maxRate increase | User requested to skip |
| systemd service | User requested to skip |
| CPU governor | Not available in LXC container |

## Verification

Check current process status:
```bash
# Show nice value and CPU core
ps -eo pid,ni,pri,psr,comm | grep etlded

# Show CPU affinity (should be mask: 3 = cores 0,1)
pgrep etlded | xargs -I{} taskset -p {}

# Check UDP buffers
sysctl net.ipv4.udp_rmem_min net.ipv4.udp_wmem_min

# Check startup log
tail -5 /home/et/start_servers.log
```

Expected output after optimization:
```
PID  NI PRI PSR COMMAND
XXXXX  0  19   0 etlded.x86_64    # PSR should be 0 or 1

pid XXXXX's current affinity mask: 3

net.ipv4.udp_rmem_min = 16384
net.ipv4.udp_wmem_min = 16384

server started (optimized) on 2026-01-25 15:46:07
```

## Backups

All original files backed up to: `/home/et/backups/2026-01-25/`

| File | Backup |
|------|--------|
| etdaemon.sh | `/home/et/backups/2026-01-25/etdaemon.sh.bak` |
| 99-etlegacy.conf | `/home/et/backups/2026-01-25/99-etlegacy.conf` |

## Rollback Procedures

### Revert startup script:
```bash
cp /home/et/backups/2026-01-25/etdaemon.sh.bak /home/et/etlegacy-v2.83.1-x86_64/etdaemon.sh
pkill -f etdaemon.sh
pkill etlded.x86_64
nohup /home/et/etlegacy-v2.83.1-x86_64/etdaemon.sh >> /home/et/etdaemon.log 2>&1 &
```

### Revert sysctl settings:
```bash
sudo rm /etc/sysctl.d/99-etlegacy.conf
sudo sysctl -w net.ipv4.udp_rmem_min=4096 net.ipv4.udp_wmem_min=4096
```

## Technical Notes

### Why CPU Affinity > Nice Priority

1. **Cache Locality:** Pinning to cores 0,1 keeps L1/L2 cache hot for the game server
2. **Reduced Jitter:** No random core migrations = more consistent frame times
3. **Nice is overkill:** Server is the primary workload; no CPU competition anyway

### LXC Container Limitations

The server runs in an LXC container, which means:
- Kernel-level network settings (rmem_max, wmem_max) are controlled by host
- CPU governor is controlled by host
- Process-level settings (nice, taskset, ulimits) work normally

### UDP Buffer Sizing

- Default 4KB buffers can cause drops during player spikes
- 16KB minimum gives headroom for 20+ player games
- Game packets are small (~100-500 bytes) but frequent (40+ per second per player)

## SSH Access Reference

```bash
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@puran.hehe.si
```

## Related Files

- Startup script: `/home/et/etlegacy-v2.83.1-x86_64/etdaemon.sh`
- Server config: `/home/et/etlegacy-v2.83.1-x86_64/etmain/vektor.cfg`
- Sysctl config: `/etc/sysctl.d/99-etlegacy.conf`
- Start log: `/home/et/start_servers.log`
- Daemon log: `/home/et/etdaemon.log`
