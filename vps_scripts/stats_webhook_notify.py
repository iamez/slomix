#!/usr/bin/env python3
"""
ET:Legacy Stats Webhook Trigger (VPS Side)

Watches for new stats files and sends webhook notification to trigger bot processing.
VPS detects file → Posts to control channel → Bot sees message → Downloads & posts stats.

This is the "trigger" half of the system:
- VPS: Detects file, sends webhook with filename
- Bot: Sees webhook, downloads file via SSH, parses, imports DB, posts rich stats

Setup on VPS:
1. Copy to: /home/et/scripts/stats_webhook_notify.py
2. Create state directory: mkdir -p /home/et/scripts/state
3. Install watchdog: pip3 install watchdog requests
4. Create systemd service (see bottom of file)
5. Set DISCORD_WEBHOOK_URL to the CONTROL CHANNEL webhook (not stats channel!)

Configuration:
- STATS_PATH: Directory where game writes stats files
- DISCORD_WEBHOOK_URL: Webhook URL for CONTROL channel (bot listens here)
- STATE_FILE: Tracks processed files across restarts
"""

import os
import sys
import json
import time
import logging
import hashlib
import threading
from datetime import datetime
from pathlib import Path

# Try to import watchdog (file system monitor)
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("ERROR: watchdog not installed. Run: pip3 install watchdog requests")
    sys.exit(1)

# Try to import requests for webhook calls
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("ERROR: requests not installed. Run: pip3 install watchdog requests")
    sys.exit(1)

# ==================== CONFIGURATION ====================
# Override with environment variables

# Path where game server writes stats files
STATS_PATH = os.environ.get(
    "STATS_PATH",
    "/home/et/.etlegacy/legacy/gamestats"
)

# Discord webhook URL (from Discord channel settings → Integrations → Webhooks)
DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    ""  # MUST be set via env or config file
)

# State file to track processed files (survives restarts)
STATE_DIR = os.environ.get(
    "STATE_DIR",
    "/home/et/scripts/state"
)
STATE_FILE = os.path.join(STATE_DIR, "processed_files.json")

# Bot notification webhook (optional - for pinging the bot)
BOT_NOTIFICATION_URL = os.environ.get(
    "BOT_NOTIFICATION_URL",
    ""  # Optional: separate webhook for bot to consume
)

# Minimum file size to consider valid (bytes)
MIN_FILE_SIZE = 100

# Delay after file creation before processing (seconds)
# Game may still be writing to the file
PROCESS_DELAY = 3

# State flush tuning (reduces disk writes on bursty rounds)
STATE_SAVE_INTERVAL_SECONDS = max(
    1, int(os.environ.get("STATE_SAVE_INTERVAL_SECONDS", "5"))
)
STATE_SAVE_BATCH_SIZE = max(
    1, int(os.environ.get("STATE_SAVE_BATCH_SIZE", "5"))
)

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/home/et/scripts/webhook_notify.log")
    ]
)
logger = logging.getLogger(__name__)
_state_lock = threading.Lock()
_state_dirty_count = 0
_state_last_flush_unix = 0.0

# ==================== STATE MANAGEMENT ====================

def load_state() -> dict:
    """Load processed files state from disk."""
    global _state_dirty_count, _state_last_flush_unix
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                loaded = json.load(f)
                if not isinstance(loaded, dict):
                    loaded = {}
                loaded.setdefault("processed_files", [])
                loaded.setdefault("last_updated", None)
                with _state_lock:
                    _state_dirty_count = 0
                    _state_last_flush_unix = time.time()
                return loaded
    except Exception as e:
        logger.warning(f"Failed to load state file: {e}")
    with _state_lock:
        _state_dirty_count = 0
        _state_last_flush_unix = time.time()
    return {"processed_files": [], "last_updated": None}


def save_state(state: dict, force: bool = False) -> bool:
    """Save processed files state to disk.

    Returns True when a flush happened, False when skipped.
    """
    global _state_dirty_count, _state_last_flush_unix
    try:
        now = time.time()
        with _state_lock:
            has_pending = _state_dirty_count > 0
            due_by_time = (now - _state_last_flush_unix) >= STATE_SAVE_INTERVAL_SECONDS
            due_by_batch = _state_dirty_count >= STATE_SAVE_BATCH_SIZE
            if not force and not (has_pending and (due_by_time or due_by_batch)):
                return False

            state["last_updated"] = datetime.now().isoformat()
            state["processed_files"] = state.get("processed_files", [])[-1000:]
            state_snapshot = {
                "processed_files": list(state["processed_files"]),
                "last_updated": state["last_updated"],
            }

        os.makedirs(STATE_DIR, exist_ok=True)
        temp_state_file = f"{STATE_FILE}.tmp"
        with open(temp_state_file, 'w') as f:
            json.dump(state_snapshot, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_state_file, STATE_FILE)
        with _state_lock:
            _state_dirty_count = 0
            _state_last_flush_unix = now
        return True
    except Exception as e:
        logger.error(f"Failed to save state file: {e}")
        return False


def is_file_processed(state: dict, filename: str) -> bool:
    """Check if file has already been processed."""
    with _state_lock:
        return filename in state.get("processed_files", [])


def mark_file_processed(state: dict, filename: str):
    """Mark file as processed and save state."""
    global _state_dirty_count
    should_flush_now = False
    with _state_lock:
        if filename in state.get("processed_files", []):
            return
        state.setdefault("processed_files", []).append(filename)
        # Keep only last 1000 files to prevent infinite growth
        if len(state["processed_files"]) > 1000:
            state["processed_files"] = state["processed_files"][-1000:]
        _state_dirty_count += 1
        should_flush_now = _state_dirty_count >= STATE_SAVE_BATCH_SIZE
    save_state(state, force=should_flush_now)

# ==================== FILE VALIDATION ====================

def is_valid_stats_file(filepath: str) -> bool:
    """
    Validate that file is a valid ET:Legacy stats file.

    Valid formats:
    - YYYY-MM-DD-HHMMSS-mapname-round-N.txt (main stats)
    - YYYY-MM-DD-HHMMSS-mapname-round-N-endstats.txt (awards)

    Examples:
    - 2025-12-07-201530-supply-round-1.txt
    - 2025-12-07-201530-supply-round-1-endstats.txt
    """
    filename = os.path.basename(filepath)

    # Must be .txt
    if not filename.endswith('.txt'):
        return False

    # Must contain 'round'
    if 'round' not in filename.lower():
        return False

    # Must start with date pattern
    parts = filename.split('-')
    if len(parts) < 6:
        return False

    # Validate date parts
    try:
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        if not (2020 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31):
            return False
    except (ValueError, IndexError):
        return False

    return True


def is_endstats_file(filepath: str) -> bool:
    """Check if file is an endstats file (awards/VS stats)."""
    filename = os.path.basename(filepath)
    return filename.endswith('-endstats.txt')


def get_file_hash(filepath: str) -> str:
    """Get SHA256 hash of file contents."""
    try:
        with open(filepath, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return "unknown"

# ==================== DISCORD WEBHOOK ====================

def send_discord_notification(filename: str, filepath: str):
    """
    Send trigger notification to Discord control channel.

    Bot will see this message and:
    1. Download the file via SSH
    2. Parse and import to database
    3. Post rich stats embed to production channel
    4. Delete this trigger message

    File types:
    - 📊 Main stats file (round-N.txt) → Player statistics
    - 🏆 Endstats file (round-N-endstats.txt) → Awards & VS stats
    """
    if not DISCORD_WEBHOOK_URL:
        logger.error("DISCORD_WEBHOOK_URL not configured!")
        return False

    try:
        # Determine file type
        is_endstats = is_endstats_file(filepath)

        # Parse filename for details
        # Format: 2025-12-07-201530-supply-round-1.txt or ...-round-1-endstats.txt
        basename = os.path.basename(filename)
        # Remove -endstats.txt or .txt suffix for parsing
        clean_name = basename.replace('-endstats.txt', '').replace('.txt', '')
        parts = clean_name.split('-')

        map_name = "Unknown"
        round_num = "?"
        if len(parts) >= 7:
            # Extract map name (between timestamp and 'round')
            timestamp_end = 4  # YYYY-MM-DD-HHMMSS is 4 parts
            round_idx = None
            for i, p in enumerate(parts):
                if p.lower() == 'round':
                    round_idx = i
                    break

            if round_idx:
                map_name = '-'.join(parts[timestamp_end:round_idx])
                if round_idx + 1 < len(parts):
                    round_num = parts[round_idx + 1]

        # Get file size for logging
        file_size = os.path.getsize(filepath)

        # Different emoji and title based on file type
        if is_endstats:
            emoji = "🏆"
            title = "🏆 Awards Ready"
            color = 0xf1c40f  # Gold for awards
            description = f"**{map_name}** - Round {round_num} Awards"
        else:
            emoji = "📊"
            title = "⚡ Round Complete"
            color = 0x3498db  # Blue for stats
            description = f"**{map_name}** - Round {round_num}"

        # Minimal trigger payload - bot will do the rich formatting
        # The important part is the filename in backticks for bot to parse
        payload = {
            "username": "ET:Legacy Stats",
            "content": f"{emoji} `{filename}`",
            "embeds": [{
                "title": title,
                "description": description,
                "color": color,
                "footer": {"text": f"{file_size:,} bytes | Triggering bot..."}
            }]
        }

        # Send webhook
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10
        )

        if response.status_code in (200, 204):
            file_type = "endstats" if is_endstats else "stats"
            logger.info(f"✅ Trigger sent ({file_type}): {filename}")
            return True
        else:
            logger.error(
                f"❌ Webhook failed: {response.status_code} - "
                f"{response.text[:200]}"
            )
            return False

    except requests.Timeout:
        logger.error(f"❌ Discord webhook timeout for {filename}")
        return False
    except Exception as e:
        logger.error(f"❌ Discord webhook error: {e}")
        return False


# ==================== FILE WATCHER ====================


class StatsFileHandler(FileSystemEventHandler):
    """Handles file system events for stats directory."""
    
    def __init__(self, state: dict):
        self.state = state
        super().__init__()
    
    def on_created(self, event):
        """Handle new file creation."""
        if event.is_directory:
            return
        
        filepath = event.src_path
        filename = os.path.basename(filepath)
        
        logger.info(f"📁 File detected: {filename}")
        
        # Validate stats file
        if not is_valid_stats_file(filepath):
            logger.debug(f"⏭️ Skipping non-stats file: {filename}")
            return
        
        # Check if already processed
        if is_file_processed(self.state, filename):
            logger.debug(f"⏭️ Already processed: {filename}")
            return
        
        # Wait for file to finish writing
        logger.info(f"⏳ Waiting {PROCESS_DELAY}s for file to complete...")
        time.sleep(PROCESS_DELAY)
        
        # Verify file size
        try:
            file_size = os.path.getsize(filepath)
            if file_size < MIN_FILE_SIZE:
                logger.warning(
                    f"⚠️ File too small ({file_size} bytes): {filename}"
                )
                return
        except OSError:
            logger.error(f"❌ Cannot read file: {filename}")
            return
        
        # Send Discord notification
        logger.info(f"📤 Sending notification for: {filename}")
        if send_discord_notification(filename, filepath):
            mark_file_processed(self.state, filename)
            logger.info(f"✅ Processed: {filename}")
        else:
            logger.error(f"❌ Failed to notify: {filename}")


# ==================== MAIN ====================


def scan_existing_files(state: dict, stats_path: str, max_age_hours: int = 48):
    """
    Scan for any unprocessed files on startup.
    Catches files created while the service was down.

    Only processes files from the last max_age_hours (default 48h)
    to avoid spamming old files on fresh deployments.
    """
    logger.info(f"🔍 Scanning for existing files in {stats_path} (last {max_age_hours}h)...")

    try:
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        files = sorted(Path(stats_path).glob("*.txt"))
        new_count = 0
        skipped_old = 0

        for filepath in files:
            filename = filepath.name

            if not is_valid_stats_file(str(filepath)):
                continue

            # Check file age - skip files older than cutoff
            try:
                file_mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                if file_mtime < cutoff_time:
                    skipped_old += 1
                    continue
            except OSError:
                continue

            if is_file_processed(state, filename):
                continue

            # Process unprocessed file
            logger.info(f"📤 Found unprocessed file: {filename}")
            if send_discord_notification(filename, str(filepath)):
                mark_file_processed(state, filename)
                new_count += 1
                # Small delay between notifications to avoid rate limiting
                time.sleep(1)

        logger.info(f"✅ Startup scan complete: {new_count} new files processed, {skipped_old} old files skipped")

    except Exception as e:
        logger.error(f"❌ Error scanning existing files: {e}")


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("🚀 ET:Legacy Stats Webhook Notifier Starting")
    logger.info("=" * 60)
    
    # Validate configuration
    if not DISCORD_WEBHOOK_URL:
        logger.error("❌ DISCORD_WEBHOOK_URL not set!")
        logger.error("   Set via environment variable or edit this script")
        sys.exit(1)
    
    if not os.path.exists(STATS_PATH):
        logger.error(f"❌ Stats directory not found: {STATS_PATH}")
        sys.exit(1)
    
    logger.info(f"📂 Watching: {STATS_PATH}")
    logger.info(f"📋 State file: {STATE_FILE}")
    logger.info(f"🔗 Webhook configured: {DISCORD_WEBHOOK_URL[:50]}...")
    
    # Load state
    state = load_state()
    processed_count = len(state.get("processed_files", []))
    logger.info(f"📊 Loaded state: {processed_count} files previously processed")
    
    # Scan for existing unprocessed files
    scan_existing_files(state, STATS_PATH)
    
    # Set up file watcher
    event_handler = StatsFileHandler(state)
    observer = Observer()
    observer.schedule(event_handler, STATS_PATH, recursive=False)
    
    logger.info("👀 Starting file watcher...")
    observer.start()
    
    try:
        logger.info("✅ Webhook notifier running. Press Ctrl+C to stop.")
        while True:
            save_state(state, force=False)
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        observer.stop()
    finally:
        save_state(state, force=True)

    observer.join()
    logger.info("👋 Goodbye!")


if __name__ == "__main__":
    main()


# ==================== SYSTEMD SERVICE ====================
"""
Create /etc/systemd/system/et-stats-webhook.service with:

[Unit]
Description=ET:Legacy Stats Webhook Notifier
After=network.target

[Service]
Type=simple
User=et
WorkingDirectory=/home/et/scripts
Environment="STATS_PATH=/home/et/.etlegacy/legacy/gamestats"
Environment="DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
Environment="STATE_DIR=/home/et/scripts/state"
ExecStart=/usr/bin/python3 /home/et/scripts/stats_webhook_notify.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

Then:
sudo systemctl daemon-reload
sudo systemctl enable et-stats-webhook
sudo systemctl start et-stats-webhook
sudo systemctl status et-stats-webhook
journalctl -u et-stats-webhook -f  # Follow logs
"""
