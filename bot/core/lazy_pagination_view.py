"""
Lazy Loading Pagination View for Large Datasets
================================================

Loads data on-demand instead of pre-generating all pages.
Perfect for: Sessions with 1000+ records, Leaderboards with 500+ players

Features:
- Only loads page when user clicks button
- Memory efficient (only stores loaded pages in cache)
- Maintains cache for recently viewed pages
- Auto-timeout after 3 minutes
- Graceful handling when data fetcher is slow

Usage:
    async def page_fetcher(page_num: int) -> discord.Embed:
        # Fetch and return embed for this page number
        return embed
    
    view = LazyPaginationView(
        ctx, 
        page_fetcher,
        total_pages=50,
        timeout=180
    )
    initial_embed = await view.get_page(0)
    message = await ctx.send(embed=initial_embed, view=view)
    view.message = message

Author: ET:Legacy Stats Bot
Date: November 7, 2025
"""

import discord
from discord.ui import View, Button
from discord import ButtonStyle, Interaction
from typing import Callable, Optional


class LazyPaginationView(View):
    """Lazy-loading pagination - loads pages on demand"""
    
    def __init__(self,
                 ctx,
                 page_fetcher: Callable,
                 total_pages: int = 5,
                 timeout: int = 180):
        """
        Initialize lazy pagination view

        Args:
            ctx: Command context (for author check)
            page_fetcher: Async function(page_num) -> discord.Embed
            total_pages: Total number of pages available
            timeout: Seconds before buttons auto-disable
        """
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.page_fetcher = page_fetcher
        self.total_pages = total_pages
        self.current_page = 0
        self.message = None
        self.page_cache = {}  # Cache loaded pages
        self.loading = False  # Prevent double-clicks during load

        self._update_buttons()

    def _update_buttons(self):
        """Update button enabled/disabled states"""
        self.first_button.disabled = (self.current_page == 0)
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.total_pages - 1)
        self.last_button.disabled = (self.current_page >= self.total_pages - 1)

    async def get_page(self, page_num: int) -> discord.Embed:
        """
        Fetch (or retrieve from cache) page embed

        Args:
            page_num: Page number to fetch (0-indexed)

        Returns:
            discord.Embed for the requested page
        """
        if page_num in self.page_cache:
            return self.page_cache[page_num]

        # Load from data fetcher
        embed = await self.page_fetcher(page_num)
        self.page_cache[page_num] = embed
        return embed

    async def update_message(self, interaction: Interaction):
        """Update message with current page"""
        if self.loading:
            return  # Prevent double-clicks

        self.loading = True
        try:
            self._update_buttons()
            embed = await self.get_page(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
        finally:
            self.loading = False

    @discord.ui.button(
        emoji="⏮️",
        style=ButtonStyle.primary,
        custom_id="lazy_first"
    )
    async def first_button(self, interaction: Interaction, button: Button):
        """Jump to first page"""
        self.current_page = 0
        await self.update_message(interaction)

    @discord.ui.button(
        label="◀️ Prev",
        style=ButtonStyle.secondary,
        custom_id="lazy_prev"
    )
    async def prev_button(self, interaction: Interaction, button: Button):
        """Go to previous page"""
        self.current_page = max(0, self.current_page - 1)
        await self.update_message(interaction)

    @discord.ui.button(
        label="Next ▶️",
        style=ButtonStyle.secondary,
        custom_id="lazy_next"
    )
    async def next_button(self, interaction: Interaction, button: Button):
        """Go to next page"""
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        await self.update_message(interaction)

    @discord.ui.button(
        emoji="⏭️",
        style=ButtonStyle.primary,
        custom_id="lazy_last"
    )
    async def last_button(self, interaction: Interaction, button: Button):
        """Jump to last page"""
        self.current_page = self.total_pages - 1
        await self.update_message(interaction)

    async def on_timeout(self):
        """Called when view times out - disable all buttons"""
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.errors.NotFound:
                pass  # Message was deleted
            except Exception:
                pass  # Other error, ignore

    async def interaction_check(self, interaction: Interaction) -> bool:
        """
        Security check: Only command author can use buttons

        Args:
            interaction: Discord interaction to check

        Returns:
            True if allowed, False otherwise
        """
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "❌ These buttons aren't for you! Run the command yourself.",
                ephemeral=True
            )
            return False
        return True
