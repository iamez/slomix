#!/usr/bin/env python3
"""
Enhanced sync_stats command with time period filtering
Replace the existing sync_stats command in ultimate_bot.py (starting at line 838)
"""

from datetime import datetime, timedelta
import re

# ============== HELPER FUNCTION ==============

def parse_time_period(period_str):
    """
    Parse time period string like '2weeks', '1day', '1month', '1year'
    Returns number of days to look back
    
    Examples:
        '2weeks' -> 14
        '1day' -> 1
        '3days' -> 3
        '1month' -> 30
        '2months' -> 60
        '1year' -> 365
        None or 'all' -> None (no filter)
    """
    if not period_str or period_str.lower() == 'all':
        return None
    
    # Parse pattern: <number><unit>
    match = re.match(r'(\d+)\s*(day|days|week|weeks|month|months|year|years|d|w|m|y)s?', 
                     period_str.lower())
    
    if not match:
        return None
    
    number = int(match.group(1))
    unit = match.group(2)
    
    # Convert to days
    if unit in ('day', 'days', 'd'):
        return number
    elif unit in ('week', 'weeks', 'w'):
        return number * 7
    elif unit in ('month', 'months', 'm'):
        return number * 30  # Approximate
    elif unit in ('year', 'years', 'y'):
        return number * 365  # Approximate
    
    return None


def should_include_file(filename, days_back=None):
    """
    Check if a stats file should be included based on date
    
    Filename format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
    
    Args:
        filename: The stats filename
        days_back: Number of days to look back (None = include all)
    
    Returns:
        True if file should be included, False otherwise
    """
    if days_back is None:
        return True
    
    try:
        # Extract date from filename (YYYY-MM-DD)
        parts = filename.split('-')
        if len(parts) < 3:
            return True  # Can't parse, include it
        
        date_str = '-'.join(parts[:3])
        file_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Include if file is newer than cutoff
        return file_date >= cutoff_date
        
    except (ValueError, IndexError):
        # If we can't parse the date, include the file
        return True


# ============== ENHANCED SYNC_STATS COMMAND ==============

@commands.command(name="sync_stats", aliases=["syncstats", "sync_logs"])
async def sync_stats(self, ctx, period: str = None):
    """
    🔄 Manually sync and process stats files from server
    
    Usage:
        !sync_stats              - Sync all unprocessed files
        !sync_stats 1day         - Sync files from last 24 hours
        !sync_stats 2days        - Sync files from last 2 days
        !sync_stats 1week        - Sync files from last 7 days
        !sync_stats 2weeks       - Sync files from last 14 days (default)
        !sync_stats 1month       - Sync files from last 30 days
        !sync_stats 3months      - Sync files from last 90 days
        !sync_stats 1year        - Sync files from last year
        !sync_stats all          - Sync ALL unprocessed files (no filter)
    
    Examples:
        !sync_stats 3d           - Last 3 days (shorthand)
        !sync_stats 2w           - Last 2 weeks (shorthand)
        !sync_stats 1m           - Last 1 month (shorthand)
    """
    try:
        if not self.bot.ssh_enabled:
            await ctx.send(
                "❌ SSH monitoring is not enabled. "
                "Set `SSH_ENABLED=true` in .env file."
            )
            return

        # Parse time period
        days_back = parse_time_period(period) if period else 14  # Default: 2 weeks
        
        # Build status message
        if days_back:
            period_display = f"last {days_back} days"
            if days_back == 1:
                period_display = "last 24 hours"
            elif days_back == 7:
                period_display = "last week"
            elif days_back == 14:
                period_display = "last 2 weeks"
            elif days_back == 30:
                period_display = "last month"
            elif days_back == 365:
                period_display = "last year"
        else:
            period_display = "all time (no filter)"

        # Send initial message
        status_msg = await ctx.send(
            f"🔄 Checking remote server for new stats files...\n"
            f"📅 Time period: **{period_display}**"
        )

        # Build SSH config
        ssh_config = {
            "host": os.getenv("SSH_HOST"),
            "port": int(os.getenv("SSH_PORT", 22)),
            "user": os.getenv("SSH_USER"),
            "key_path": os.getenv("SSH_KEY_PATH", ""),
            "remote_path": os.getenv("REMOTE_STATS_PATH"),
        }

        # List remote files
        remote_files = await self.bot.ssh_list_remote_files(ssh_config)

        if not remote_files:
            await status_msg.edit(
                content="❌ Could not connect to server or no files found."
            )
            return

        # Filter files by time period
        if days_back:
            filtered_files = [f for f in remote_files if should_include_file(f, days_back)]
            excluded_count = len(remote_files) - len(filtered_files)
            remote_files = filtered_files
            
            if excluded_count > 0:
                await status_msg.edit(
                    content=(
                        f"🔄 Checking remote server...\n"
                        f"📅 Time period: **{period_display}**\n"
                        f"📊 Found **{len(remote_files)}** files in period "
                        f"({excluded_count} older files excluded)"
                    )
                )

        # Check which files need processing
        files_to_process = []
        for filename in remote_files:
            if await self.bot.should_process_file(filename):
                files_to_process.append(filename)

        if not files_to_process:
            await status_msg.edit(
                content=(
                    f"✅ All files from {period_display} are already processed!\n"
                    f"Nothing new to sync."
                )
            )
            return

        # Sort files: Round 1 before Round 2, chronologically
        # Format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
        def sort_key(filename):
            parts = filename.split("-")
            if len(parts) >= 7:
                date = "-".join(parts[:3])  # YYYY-MM-DD
                time = parts[3]  # HHMMSS
                round_num = parts[-1].replace(".txt", "")  # N from round-N
                return (
                    date,
                    time,
                    round_num,
                )  # Sort by date, time, then round
            return (filename, "", "99")  # Fallback

        files_to_process.sort(key=sort_key)

        # Phase 1: Download ALL files first
        await status_msg.edit(
            content=(
                f"📥 Downloading {len(files_to_process)} file(s)...\n"
                f"📅 Period: {period_display}"
            )
        )

        downloaded_files = []
        download_failed = 0

        for i, filename in enumerate(files_to_process):
            try:
                # Download file
                local_path = await self.bot.ssh_download_file(
                    ssh_config, filename, "local_stats"
                )

                if local_path:
                    downloaded_files.append((filename, local_path))

                    # Update progress every 50 files
                    if (i + 1) % 50 == 0:
                        await status_msg.edit(
                            content=f"📥 Downloading... {i + 1}/{len(files_to_process)}"
                        )
                else:
                    download_failed += 1
                    logger.warning(f"Failed to download {filename}")

            except Exception as e:
                logger.error(f"Download error for {filename}: {e}")
                download_failed += 1

        # Phase 2: Verify downloads
        await status_msg.edit(
            content=f"🔍 Verifying downloads... {len(downloaded_files)} files"
        )

        local_files = set(os.listdir("local_stats"))
        verified_files = []

        for filename, local_path in downloaded_files:
            if os.path.basename(local_path) in local_files:
                verified_files.append((filename, local_path))
            else:
                logger.error(f"Downloaded file missing: {filename}")
                download_failed += 1

        logger.info(
            f"✅ Downloaded {len(verified_files)} files, "
            f"{download_failed} failed"
        )

        if not verified_files:
            await status_msg.edit(
                content="❌ No files were successfully downloaded."
            )
            return

        # Phase 3: Process/parse files for database import
        await status_msg.edit(
            content=f"⚙️ Processing {len(verified_files)} file(s) for database import..."
        )

        processed = 0
        process_failed = 0

        for i, (filename, local_path) in enumerate(verified_files):
            try:
                # Process the file (parse + import)
                result = await self.bot.process_gamestats_file(
                    local_path, filename
                )

                if result.get("success"):
                    processed += 1
                else:
                    process_failed += 1
                    logger.error(
                        f"Processing failed for {filename}: {result.get('error')}"
                    )

                # Update progress every 50 files
                if (i + 1) % 50 == 0:
                    await status_msg.edit(
                        content=f"⚙️ Processing... {i + 1}/{len(verified_files)}"
                    )

            except Exception as e:
                logger.error(f"Failed to process {filename}: {e}")
                process_failed += 1

        # Final status
        embed = discord.Embed(
            title="✅ Stats Sync Complete!",
            color=0x00FF00,
            timestamp=datetime.now(),
        )
        embed.add_field(
            name="📅 Time Period",
            value=f"**{period_display}**",
            inline=False,
        )
        embed.add_field(
            name="📥 Download Phase",
            value=(
                f"✅ Downloaded: **{len(verified_files)}** file(s)\n"
                f"❌ Failed: **{download_failed}** file(s)"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚙️ Processing Phase",
            value=(
                f"✅ Processed: **{processed}** file(s)\n"
                f"❌ Failed: **{process_failed}** file(s)"
            ),
            inline=False,
        )

        if processed > 0:
            embed.add_field(
                name="💡 What's Next?",
                value=(
                    "Round summaries have been posted above!\n"
                    "Use `!last_session` or `!last_session graphs` to see full details."
                ),
                inline=False,
            )
        
        embed.set_footer(text="💡 Tip: Use !sync_stats 1day for today's matches only")

        await status_msg.edit(content=None, embed=embed)
        logger.info(
            f"✅ Manual sync complete ({period_display}): "
            f"{len(verified_files)} downloaded, "
            f"{processed} processed, {process_failed} failed"
        )

    except Exception as e:
        logger.exception(f"Error in sync_stats: {e}")
        await ctx.send(f"❌ Error during sync: {e}")


# ============== QUICK SHORTCUT COMMANDS ==============

@commands.command(name="sync_today", aliases=["sync1day"])
async def sync_today(self, ctx):
    """🔄 Quick sync: Today's matches only (last 24 hours)"""
    await self.sync_stats(ctx, period="1day")


@commands.command(name="sync_week", aliases=["sync1week"])
async def sync_week(self, ctx):
    """🔄 Quick sync: This week's matches (last 7 days)"""
    await self.sync_stats(ctx, period="1week")


@commands.command(name="sync_month", aliases=["sync1month"])
async def sync_month(self, ctx):
    """🔄 Quick sync: This month's matches (last 30 days)"""
    await self.sync_stats(ctx, period="1month")


@commands.command(name="sync_all")
async def sync_all(self, ctx):
    """🔄 Quick sync: ALL unprocessed files (no time filter)"""
    await self.sync_stats(ctx, period="all")
