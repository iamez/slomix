"""
Endstats Pagination View
========================

Specialized pagination for endstats pages with:
- First/Prev/Page/Next/Last navigation
- Map/Round view toggle
- Page indicator in the middle button
"""

from __future__ import annotations

import discord
from discord.ui import View, Button
from discord import ButtonStyle, Interaction
from typing import List
import logging

logger = logging.getLogger("bot.core.endstats_pagination_view")


class EndstatsPaginationView(View):
    """Pagination view for endstats (map view + round view)."""

    def __init__(
        self,
        ctx,
        map_pages: List[discord.Embed],
        round_pages: List[discord.Embed],
        timeout: int = 180,
    ):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.map_pages = map_pages
        self.round_pages = round_pages
        self.mode = "map"
        self.current_page = 0
        self.message = None
        self._update_buttons()

    def _get_pages(self) -> List[discord.Embed]:
        return self.map_pages if self.mode == "map" else self.round_pages

    def _update_buttons(self):
        pages = self._get_pages()
        total_pages = len(pages)
        self.first_button.disabled = (self.current_page == 0 or total_pages <= 1)
        self.prev_button.disabled = (self.current_page == 0 or total_pages <= 1)
        self.next_button.disabled = (self.current_page >= total_pages - 1 or total_pages <= 1)
        self.last_button.disabled = (self.current_page >= total_pages - 1 or total_pages <= 1)

        # Update page indicator label
        if total_pages <= 0:
            self.page_button.label = "0/0"
        else:
            self.page_button.label = f"{self.current_page + 1}/{total_pages}"

        # Toggle label
        self.toggle_button.label = "Map View" if self.mode == "round" else "Round View"

    def _decorate_embed(self, embed: discord.Embed) -> discord.Embed:
        total_pages = len(self._get_pages())
        footer = f"{self.mode.title()} View • Page {self.current_page + 1}/{max(total_pages, 1)}"
        embed.set_footer(text=footer)
        return embed

    async def update_message(self, interaction: Interaction):
        self._update_buttons()
        pages = self._get_pages()
        if not pages:
            if not interaction.response.is_done():
                await interaction.response.defer()
            return
        embed = self._decorate_embed(pages[self.current_page])
        try:
            if interaction.response.is_done():
                await interaction.message.edit(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        except discord.InteractionResponded:
            # Response already sent; fall back to direct message edit
            try:
                await interaction.message.edit(embed=embed, view=self)
            except Exception as e:
                logger.debug(f"Endstats pagination fallback edit failed: {e}")
        except discord.NotFound:
            # Interaction token expired or message deleted; best-effort fallback
            try:
                await interaction.message.edit(embed=embed, view=self)
            except Exception as e:
                logger.debug(f"Endstats pagination NotFound fallback failed: {e}")
        except discord.HTTPException as e:
            # If the response window closed, defer then edit the message directly
            if not interaction.response.is_done():
                try:
                    await interaction.response.defer()
                except Exception:
                    pass
            try:
                await interaction.message.edit(embed=embed, view=self)
            except Exception as inner:
                logger.warning(f"Failed to update endstats pagination message: {inner} (original: {e})")

    @discord.ui.button(emoji="⏮️", style=ButtonStyle.primary, custom_id="endstats_first", row=0)
    async def first_button(self, interaction: Interaction, button: Button):
        self.current_page = 0
        await self.update_message(interaction)

    @discord.ui.button(label="◀️", style=ButtonStyle.secondary, custom_id="endstats_prev", row=0)
    async def prev_button(self, interaction: Interaction, button: Button):
        self.current_page = max(0, self.current_page - 1)
        await self.update_message(interaction)

    @discord.ui.button(label="1/1", style=ButtonStyle.secondary, custom_id="endstats_page", row=0, disabled=True)
    async def page_button(self, interaction: Interaction, button: Button):
        # Disabled indicator button (no action)
        await interaction.response.defer()

    @discord.ui.button(label="▶️", style=ButtonStyle.secondary, custom_id="endstats_next", row=0)
    async def next_button(self, interaction: Interaction, button: Button):
        pages = self._get_pages()
        self.current_page = min(len(pages) - 1, self.current_page + 1)
        await self.update_message(interaction)

    @discord.ui.button(emoji="⏭️", style=ButtonStyle.primary, custom_id="endstats_last", row=0)
    async def last_button(self, interaction: Interaction, button: Button):
        pages = self._get_pages()
        self.current_page = max(0, len(pages) - 1)
        await self.update_message(interaction)

    @discord.ui.button(label="Round View", style=ButtonStyle.success, custom_id="endstats_toggle", row=1)
    async def toggle_button(self, interaction: Interaction, button: Button):
        # Switch mode and reset to page 0
        self.mode = "round" if self.mode == "map" else "map"
        self.current_page = 0
        await self.update_message(interaction)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.errors.NotFound:
                logger.debug("Message was deleted, cannot disable buttons")
            except Exception as e:
                logger.warning(f"Failed to disable buttons on timeout: {e}")

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "❌ These buttons aren't for you! Run the command yourself to get your own navigation.",
                ephemeral=True
            )
            return False
        return True
