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
 
    @commands.command()
    @check.is_verified_guild()
    @commands.has_permissions(administrator=True)
    async def ban(self, ctx: commands.Context, user: discord.User = None): # type: ignore
            user = user or ctx.author
    
            try:
                assert ctx.guild is not None
                await self.bot.db.execute(
                    "INSERT INTO banned_users (guild_id, user_id) VALUES (?, ?)", 
                    (ctx.guild.id, user.id)
                )
                await self.bot.db.commit()
                await ctx.send("This user is banned from ask commands!")
            except aiosqlite.IntegrityError:
                await ctx.send("This user is already banned from ask commands!")

    @ban.error
    async def ban_error(self, ctx: commands.Context, error):
        if isinstance(error, check.UnverifiedGuildError):
            await ctx.send("This server is unverified!")
                
    @commands.command()
    @check.is_verified_guild()
    @commands.has_permissions(administrator=True)
    @check.is_banned_user()
    async def unban(self, ctx: commands.Context, user: discord.User = None): # type: ignore
            user = user or ctx.author
    
            try:
                assert ctx.guild is not None
                await self.bot.db.execute(
                    "DELETE FROM banned_users where guild_id = ? AND user_id = ?", 
                    (ctx.guild.id, user.id)
                )
                await self.bot.db.commit()
                await ctx.send("This user is unbanned from ask commands!")
            except Exception as e: # noqa: BLE001
                print(e)

    @unban.error
    async def unban_error(self, ctx: commands.Context, error):
        if isinstance(error, check.UnverifiedGuildError):
            await ctx.send("This server is unverified!")
        elif isinstance(error, check.BannedUserError):
            await ctx.send("This user is already not banned!")

async def setup(bot: tncbot.TNCBot):
    await bot.add_cog(Admin(bot))
