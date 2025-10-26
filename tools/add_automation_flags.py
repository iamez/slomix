"""
Add automation enable/disable flags to bot initialization
"""
import sys

def add_automation_flags():
    bot_file = 'bot/ultimate_bot.py'
    
    # Read the file
    with open(bot_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Find the insertion point (after gather_queue line)
    insertion_index = None
    for i, line in enumerate(lines):
        if 'self.gather_queue = {' in line:
            insertion_index = i + 1
            break
    
    if insertion_index is None:
        print("❌ Could not find insertion point")
        return False
    
    # Skip blank line if present
    while insertion_index < len(lines) and lines[insertion_index].strip() == '':
        insertion_index += 1
    
    # Check if already added
    if insertion_index < len(lines) and 'automation_enabled' in lines[insertion_index]:
        print("⚠️ Automation flags already present")
        return True
    
    # Prepare new lines to insert
    new_lines = [
        '\n',
        '        # 🤖 Automation System Flags (OFF by default for dev/testing)\n',
        "        self.automation_enabled = os.getenv('AUTOMATION_ENABLED', 'false').lower() == 'true'\n",
        "        self.ssh_enabled = os.getenv('SSH_ENABLED', 'false').lower() == 'true'\n",
        '        \n',
        '        if self.automation_enabled:\n',
        '            logger.info("✅ Automation system ENABLED")\n',
        '        else:\n',
        '            logger.warning("⚠️ Automation system DISABLED (set AUTOMATION_ENABLED=true to enable)")\n',
    ]
    
    # Insert the new lines
    lines = lines[:insertion_index] + new_lines + lines[insertion_index:]
    
    # Write back
    with open(bot_file, 'w', encoding='utf-8', errors='ignore') as f:
        f.writelines(lines)
    
    print(f"✅ Added automation flags at line {insertion_index + 1}")
    print(f"📝 Total lines added: {len(new_lines)}")
    return True

if __name__ == '__main__':
    success = add_automation_flags()
    sys.exit(0 if success else 1)
