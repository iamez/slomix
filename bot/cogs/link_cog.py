"""
Link Cog - Player-Discord Account Linking
==========================================
Extracted from: bot/ultimate_bot.py (Phase 2 - Cog Extraction)
Extraction Date: 2025-11-01

Player linking system connecting Discord accounts to in-game profiles (GUIDs).
Supports smart self-linking, name search, GUID direct linking, and admin linking.

Commands:
- !link - Smart self-linking with top 3 suggestions
- !link <name> - Search by player name
- !link <GUID> - Direct link by GUID
- !link @user <GUID> - Admin link another user
- !unlink - Remove your link
- !select <1-3> - Alternative to reaction selection
- !find_player <name> - Helper: Search for players with GUIDs and aliases
- !list_players - Browse all players with pagination
- !setname <name> - Set custom display name (NEW!)
- !setname alias <name> - Use one of your aliases as display name (NEW!)
- !setname reset - Reset to automatic display name (NEW!)
- !myaliases - View all your in-game aliases (NEW!)

Enhanced Features:
- Interactive reactions (1️⃣/2️⃣/3️⃣) for easy selection
- Shows up to 3 aliases per player
- GUID validation and confirmation
- Admin linking with permissions check
- Fuzzy name matching
- Custom display names for linked players
"""

import logging

from discord.ext import commands

from bot.cogs.link_mixins.browse_mixin import _LinkBrowseMixin
from bot.cogs.link_mixins.core_mixin import _LinkCoreMixin
from bot.cogs.link_mixins.interactive_mixin import _LinkInteractiveMixin
from bot.services.player_display_name_service import PlayerDisplayNameService
from bot.services.player_formatter import PlayerFormatter

logger = logging.getLogger(__name__)


class LinkCog(
    _LinkCoreMixin,
    _LinkInteractiveMixin,
    _LinkBrowseMixin,
    commands.Cog,
    name="Link",
):
    """🔗 Player-Discord Account Linking"""

    def __init__(self, bot):
        """
        Initialize the Link Cog.

        Args:
            bot: The main bot instance with database access
        """
        self.bot = bot
        self.display_name_service = PlayerDisplayNameService(bot.db_adapter)
        self.player_formatter = PlayerFormatter(bot.db_adapter)
        self.enable_link_selection_state = getattr(
            bot.config, "enable_link_selection_state", False
        )
        self.selection_ttl_seconds = getattr(
            bot.config, "link_selection_ttl_seconds", 60
        )
        self.pending_link_selections = {}
        logger.info("🔗 LinkCog loaded")


async def setup(bot):
    """Load the Link Cog."""
    await bot.add_cog(LinkCog(bot))
