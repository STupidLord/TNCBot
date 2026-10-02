import aiosqlite
import discord
from discord.ext import commands

import bot as tncbot
import check


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot: tncbot.TNCBot = bot

    @commands.command()
    @check.is_verified_guild()
    @commands.has_permissions(administrator=True)
    async def allow_channel(self, ctx: commands.Context, channel: discord.TextChannel = None): # type: ignore
        channel = channel or ctx.channel

        try:
            assert ctx.guild is not None
            await self.bot.db.execute(
                "INSERT INTO allowed_channels (guild_id, channel_id) VALUES (?, ?)", 
                (ctx.guild.id, channel.id)
            )
            await self.bot.db.commit()
            await ctx.send("Using the bot in that channel has been allowed.")
        except aiosqlite.IntegrityError:
            await ctx.send("Using the bot in that channel is already allowed.")

    @allow_channel.error
    async def allow_channel_error(self, ctx: commands.Context, error):
        if isinstance(error, check.UnverifiedGuildError):
            await ctx.send("This server is unverified!")

    @commands.command()
    @check.is_verified_guild()
    @commands.has_permissions(administrator=True)
    @check.is_allowed_channel()
    async def disallow_channel(self, ctx: commands.Context, channel: discord.TextChannel = None): # type: ignore
        channel = channel or ctx.channel

        try:
            assert ctx.guild is not None
            await self.bot.db.execute(
                "DELETE FROM allowed_channels WHERE guild_id = ? AND channel_id = ?", 
                (ctx.guild.id, channel.id)
            )
            await self.bot.db.commit()
            await ctx.send("Using the bot in that channel has been disallowed.")
        except Exception as e: # noqa: BLE001
            print(e)

    @disallow_channel.error
    async def disallow_channel_error(self, ctx: commands.Context, error):
        if isinstance(error, check.UnverifiedGuildError):
            await ctx.send("This server is unverified!")
        if isinstance(error, check.UnAllowedChannelError):
            await ctx.send("That channel is already not allowed!")

async def setup(bot: tncbot.TNCBot):
    await bot.add_cog(Admin(bot))
