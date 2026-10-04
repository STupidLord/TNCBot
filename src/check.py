from discord.ext import commands


def is_creator():
    def predicate(ctx):
        return ctx.author.id == 766045312095617104

    return commands.check(predicate)

class UnverifiedGuildError(commands.CommandError):
    """Guild is not verified"""

def is_verified_guild():
    def predicate(ctx):
        if ctx.bot.authorized_guilds is None:
            return False

        if ctx.guild is None:
            return False
        
        if ctx.guild.id in ctx.bot.authorized_guilds:
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

class BannedUserError(commands.CommandError):
    """User is not allowed to use this command"""

def is_banned_user():
    async def predicate(ctx: commands.Context):
        if ctx.guild is None:
            return False

        async with ctx.bot.db.execute(
                "SELECT 1 FROM banned_users WHERE guild_id = ? AND user_id = ?", 
                (ctx.guild.id, ctx.author.id)
            ) as cursor:
                result = await cursor.fetchone()

        if result is not None:
            return True
        
        raise BannedUserError

    return commands.check(predicate)

def is_not_banned_user():
    async def predicate(ctx: commands.Context):
        if ctx.guild is None:
            return False

        async with ctx.bot.db.execute(
                "SELECT 1 FROM banned_users WHERE guild_id = ? AND user_id = ?", 
                (ctx.guild.id, ctx.author.id)
            ) as cursor:
                result = await cursor.fetchone()

        if result is None:
            return True
        
        raise BannedUserError

    return commands.check(predicate)
