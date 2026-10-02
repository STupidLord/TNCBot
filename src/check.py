from discord.ext import commands


class UnverifiedGuildError(commands.CommandError):
    """Guild is not verified"""

def is_verified_guild():
    def predicate(ctx):
        if ctx.bot.authorized_guilds is None:
            return False

        if ctx.guild is None:
            return False
        
        if ctx.guild in ctx.bot.authorized_guilds:
            return True

        raise UnverifiedGuildError
    
    return commands.check(predicate)
        
class UnAllowedChannelError(commands.CommandError):
    """Command is not allowed in channel"""

def is_allowed_channel():
    async def predicate(ctx):
        if ctx.guild is None:
            return False

        async with ctx.bot.db.execute(
                "SELECT 1 FROM allowed_channels WHERE guild_id = ? AND channel_id = ?", 
                (ctx.guild.id, ctx.channel.id)
            ) as cursor:
                result = await cursor.fetchone()

        if result is not None:
            return True
        
        raise UnAllowedChannelError

    return commands.check(predicate)
