"""Compare VPS files vs local files to find missing ones"""
import asyncio
import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

async def main():
    # Get local files
    local_files = set()
    for f in os.listdir('local_stats'):
        if f.endswith('.txt') and f.startswith('2025-'):
            local_files.add(f)
    
    print(f"📁 Local files: {len(local_files)}")
    
    # Connect to VPS
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        key_path = os.path.expanduser(os.getenv('SSH_KEY_PATH'))
        ssh.connect(
            hostname=os.getenv('SSH_HOST'),
            port=int(os.getenv('SSH_PORT', 22)),
            username=os.getenv('SSH_USER'),
            key_filename=key_path
        )
        
        sftp = ssh.open_sftp()
        remote_path = os.getenv('REMOTE_STATS_PATH')
        remote_files = set(sftp.listdir(remote_path))
        sftp.close()
        
        print(f"🌐 Remote files: {len(remote_files)}\n")
        
        # Find missing files
        missing = remote_files - local_files
        
        if missing:
            print(f"⚠️  MISSING {len(missing)} files from local_stats:\n")
            
            # Count by date
            from datetime import datetime, timedelta
            recent_missing = []
            old_missing = []
            cutoff = datetime.now() - timedelta(days=30)
            
            for f in sorted(missing):
                try:
                    file_date = datetime.strptime(f[:10], "%Y-%m-%d")
                    if file_date >= cutoff:
                        recent_missing.append(f)
                    else:
                        old_missing.append(f)
                except:
                    pass
            
            print(f"📅 Recent (last 30 days): {len(recent_missing)} files")
            print(f"📅 Old (>30 days ago): {len(old_missing)} files\n")
            
            if recent_missing:
                print("Recent missing files:")
                for f in recent_missing[:20]:
                    print(f"  {f}")
                if len(recent_missing) > 20:
                    print(f"  ... and {len(recent_missing) - 20} more")
            else:
                print("✅ All recent files are synced!")
                print("\nOld files sample:")
                for f in sorted(old_missing)[:20]:
                    print(f"  {f}")
                if len(old_missing) > 20:
                    print(f"  ... and {len(old_missing) - 20} more")
        else:
            print("✅ All remote files are present locally!")
        
    finally:
        ssh.close()

if __name__ == '__main__':
    asyncio.run(main())
