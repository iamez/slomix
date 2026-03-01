"""
Interactive Pagination View for Discord Embeds
===============================================

Provides button-based navigation for multi-page embeds.

Features:
- First/Previous/Next/Last page navigation
- Only command author can interact (security)
- Auto-timeout after 3 minutes of inactivity
- Buttons auto-disable at boundaries (first/last page)

Usage:
    pages = [embed1, embed2, embed3]  # List of discord.Embed objects
    view = PaginationView(ctx, pages)
    await ctx.send(embed=pages[0], view=view)

Author: ET:Legacy Stats Bot
Date: November 7, 2025
"""

import discord
from discord.ui import View, Button
from discord import ButtonStyle, Interaction
from typing import List
import logging

logger = logging.getLogger("bot.core.pagination_view")


class PaginationView(View):
    """Interactive button-based pagination for Discord embeds"""

    def __init__(self, ctx, pages: List[discord.Embed], timeout: int = 180):
        """
        Initialize pagination view

        Args:
            ctx: Command context (for author check)
            pages: List of discord.Embed objects to paginate
            timeout: Seconds before buttons auto-disable (default: 180 = 3 minutes)
        """
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.pages = pages
        self.current_page = 0
        self.message = None  # Will be set after first send

        # Disable navigation if only one page
        if len(pages) <= 1:
            self.first_button.disabled = True
            self.prev_button.disabled = True
            self.next_button.disabled = True
            self.last_button.disabled = True
        else:
            self._update_buttons()

    def _update_buttons(self):
        """Update button enabled/disabled states based on current page"""
        total_pages = len(self.pages)

        # Disable First/Prev on first page
        self.first_button.disabled = (self.current_page == 0)
        self.prev_button.disabled = (self.current_page == 0)

        # Disable Next/Last on last page
        self.next_button.disabled = (self.current_page >= total_pages - 1)
        self.last_button.disabled = (self.current_page >= total_pages - 1)

    async def update_message(self, interaction: Interaction):
        """
        Update the message to show current page

        Args:
            interaction: Discord interaction from button click
        """
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.pages[self.current_page],
            view=self
        )

    @discord.ui.button(emoji="⏮️", style=ButtonStyle.primary, custom_id="first")
    async def first_button(self, interaction: Interaction, button: Button):
        """Jump to first page"""
        self.current_page = 0
        await self.update_message(interaction)

    @discord.ui.button(label="◀️ Prev", style=ButtonStyle.secondary, custom_id="prev")
    async def prev_button(self, interaction: Interaction, button: Button):
        """Go to previous page"""
        self.current_page = max(0, self.current_page - 1)
        await self.update_message(interaction)

    @discord.ui.button(label="Next ▶️", style=ButtonStyle.secondary, custom_id="next")
    async def next_button(self, interaction: Interaction, button: Button):
        """Go to next page"""
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        await self.update_message(interaction)

    @discord.ui.button(emoji="⏭️", style=ButtonStyle.primary, custom_id="last")
    async def last_button(self, interaction: Interaction, button: Button):
        """Jump to last page"""
        self.current_page = len(self.pages) - 1
        await self.update_message(interaction)

    async def on_timeout(self):
        """Called when view times out - disable all buttons and notify user"""
        if self.message:
            try:
                for child in self.children:
                    child.disabled = True
                embed = self.message.embeds[0] if self.message.embeds else None
                if embed:
                    embed.set_footer(text="Navigation expired. Run the command again to continue.")
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass

    async def interaction_check(self, interaction: Interaction) -> bool:
        """
        Security check: Only allow original command author to use buttons

        Args:
            interaction: Discord interaction to check

        Returns:
            True if user is allowed, False otherwise
        """
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "❌ These buttons aren't for you! Run the command yourself to get your own navigation.",
                ephemeral=True
            )
            return False
        return True
