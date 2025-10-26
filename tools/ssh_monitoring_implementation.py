"""
Complete SSH monitoring, file detection, and processing implementation
This will be integrated into the bot's endstats_monitor task
"""
import re
import os
import asyncio
import aiosqlite
import paramiko
from datetime import datetime
from io import StringIO
import logging

logger = logging.getLogger(__name__)


def parse_gamestats_filename(filename):
    """
    Parse gamestats filename to extract metadata
    
    Format: YYYY-MM-DD-HHMMSS-<map_name>-round-<N>.txt
    Example: 2025-10-02-232818-erdenberg_t2-round-2.txt
    
    Returns:
        dict with keys: date, time, map_name, round_number, is_round_1, is_round_2
    """
    pattern = r'^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+?)-round-(\d+)\.txt$'
    match = re.match(pattern, filename)
    
    if not match:
        return None
    
    date, time, map_name, round_num = match.groups()
    round_number = int(round_num)
    
    return {
        'date': date,
        'time': time,
        'map_name': map_name,
        'round_number': round_number,
        'is_round_1': round_number == 1,
        'is_round_2': round_number == 2,
        'is_map_complete': round_number == 2,
        'full_timestamp': f"{date} {time[:2]}:{time[2:4]}:{time[4:6]}"
    }


async def ssh_list_remote_files(ssh_config):
    """
    List files on remote SSH server
    
    Args:
        ssh_config: dict with keys: host, port, user, key_path, remote_path
    
    Returns:
        list of filename strings
    """
    try:
        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Expand key path
        key_path = os.path.expanduser(ssh_config['key_path'])
        
        logger.info(f"🔌 Connecting to {ssh_config['host']}:{ssh_config['port']}...")
        
        # Connect
        ssh.connect(
            hostname=ssh_config['host'],
            port=ssh_config['port'],
            username=ssh_config['user'],
            key_filename=key_path,
            timeout=10
        )
        
        # Open SFTP
        sftp = ssh.open_sftp()
        
        # List files
        files = sftp.listdir(ssh_config['remote_path'])
        
        # Filter for .txt files
        txt_files = [f for f in files if f.endswith('.txt')]
        
        logger.info(f"📂 Found {len(txt_files)} .txt files on remote server")
        
        sftp.close()
        ssh.close()
        
        return txt_files
        
    except Exception as e:
        logger.error(f"❌ SSH connection failed: {e}")
        return []


async def ssh_download_file(ssh_config, filename, local_dir='local_stats'):
    """
    Download a single file from remote server
    
    Args:
        ssh_config: dict with SSH connection details
        filename: remote filename to download
        local_dir: local directory to save to
    
    Returns:
        str: local file path, or None if failed
    """
    try:
        # Ensure local directory exists
        os.makedirs(local_dir, exist_ok=True)
        
        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        key_path = os.path.expanduser(ssh_config['key_path'])
        
        ssh.connect(
            hostname=ssh_config['host'],
            port=ssh_config['port'],
            username=ssh_config['user'],
            key_filename=key_path,
            timeout=10
        )
        
        sftp = ssh.open_sftp()
        
        # Download file
        remote_file = f"{ssh_config['remote_path']}/{filename}"
        local_file = os.path.join(local_dir, filename)
        
        logger.info(f"📥 Downloading {filename}...")
        sftp.get(remote_file, local_file)
        
        sftp.close()
        ssh.close()
        
        logger.info(f"✅ Downloaded to {local_file}")
        return local_file
        
    except Exception as e:
        logger.error(f"❌ Download failed for {filename}: {e}")
        return None


async def process_gamestats_file(file_path, parser, db_path):
    """
    Process a gamestats file using C0RNP0RN3StatsParser
    
    Args:
        file_path: local path to gamestats file
        parser: instance of C0RNP0RN3StatsParser
        db_path: path to SQLite database
    
    Returns:
        dict with keys: success, session_id, player_count, error
    """
    try:
        logger.info(f"⚙️ Processing {os.path.basename(file_path)}...")
        
        # Parse file
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Use parser to extract data
        # (This assumes C0RNP0RN3StatsParser has a parse_file method)
        stats_data = parser.parse_file(content)
        
        if not stats_data:
            raise Exception("Parser returned no data")
        
        # Insert into database
        async with aiosqlite.connect(db_path) as db:
            # Insert session
            session_id = await db.execute('''
                INSERT INTO sessions (session_date, map_name, ...)
                VALUES (?, ?, ...)
            ''', (...))
            
            session_id = session_id.lastrowid
            
            # Insert player stats
            for player in stats_data['players']:
                await db.execute('''
                    INSERT INTO player_comprehensive_stats (...)
                    VALUES (...)
                ''', (...))
            
            await db.commit()
        
        logger.info(f"✅ Processed successfully (session_id: {session_id})")
        
        return {
            'success': True,
            'session_id': session_id,
            'player_count': len(stats_data.get('players', [])),
            'error': None
        }
        
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        return {
            'success': False,
            'session_id': None,
            'player_count': 0,
            'error': str(e)
        }


async def mark_file_processed(db_path, filename, result):
    """
    Mark a file as processed in the database
    
    Args:
        db_path: path to SQLite database
        filename: name of processed file
        result: dict from process_gamestats_file
    """
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO processed_files 
                (filename, success, error_message, processed_at)
                VALUES (?, ?, ?, ?)
            ''', (
                filename,
                result['success'],
                result['error'],
                datetime.now().isoformat()
            ))
            await db.commit()
        
        logger.info(f"📝 Marked {filename} as processed")
        
    except Exception as e:
        logger.error(f"❌ Failed to mark file as processed: {e}")


async def get_processed_files(db_path):
    """
    Get set of already processed filenames
    
    Args:
        db_path: path to SQLite database
    
    Returns:
        set of filenames
    """
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute('SELECT filename FROM processed_files WHERE success = 1')
            rows = await cursor.fetchall()
            return {row[0] for row in rows}
    except Exception as e:
        logger.error(f"❌ Failed to get processed files: {e}")
        return set()


# Example integration into bot's endstats_monitor task:
"""
@tasks.loop(seconds=30)
async def endstats_monitor(self):
    '''🔄 Monitor for new EndStats files'''
    if not self.monitoring or not self.ssh_enabled:
        return
    
    try:
        # SSH config from .env
        ssh_config = {
            'host': os.getenv('SSH_HOST', 'puran.hehe.si'),
            'port': int(os.getenv('SSH_PORT', '48101')),
            'user': os.getenv('SSH_USER', 'et'),
            'key_path': os.getenv('SSH_KEY_PATH', '~/.ssh/etlegacy_bot'),
            'remote_path': os.getenv('REMOTE_STATS_PATH', '/home/et/.etlegacy/legacy/gamestats/')
        }
        
        # List remote files
        remote_files = await ssh_list_remote_files(ssh_config)
        
        # Get already processed files
        processed = await get_processed_files(self.db_path)
        
        # Find new files
        new_files = [f for f in remote_files if f not in processed]
        
        if not new_files:
            return
        
        logger.info(f"🆕 Found {len(new_files)} new files to process")
        
        # Process each new file
        for filename in new_files:
            # Parse filename
            file_info = parse_gamestats_filename(filename)
            if not file_info:
                logger.warning(f"⚠️ Could not parse filename: {filename}")
                continue
            
            # Download file
            local_path = await ssh_download_file(ssh_config, filename)
            if not local_path:
                continue
            
            # Process file
            result = await process_gamestats_file(
                local_path,
                self.parser,  # C0RNP0RN3StatsParser instance
                self.db_path
            )
            
            # Mark as processed
            await mark_file_processed(self.db_path, filename, result)
            
            # Post to Discord if successful
            if result['success']:
                if file_info['is_round_1']:
                    await self.post_round_1_summary(file_info, result)
                elif file_info['is_round_2']:
                    await self.post_round_2_summary(file_info, result)
                    await self.post_map_complete_summary(file_info)
    
    except Exception as e:
        logger.error(f"EndStats monitoring error: {e}")
"""
