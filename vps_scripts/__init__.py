"""
VPS Scripts Package
===================

Scripts meant to run on the VPS game server, not on the bot server.

Available Scripts:
    ws_notify_server.py: WebSocket notification server for live stats
    stats_webhook_notify.py: Webhook notification for new stats files

These scripts run on the ET:Legacy game server and notify the bot
when new stats files are available for download.

Deployment:
    Copy these scripts to the VPS and run as systemd services.
    See docs/VPS_DEPLOYMENT_GUIDE.md for setup instructions.
"""

__all__ = []
