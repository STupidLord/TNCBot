import discord
from discord.ext import commands

import bot as tncbot


class Listen(commands.Cog):
    def __init__(self, bot):
        self.bot: tncbot.TNCBot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        if guild.owner is not None:
            print(f"Was invited to {guild.name} ({guild.id}) owned by {guild.owner.name} ({guild.owner.id})")
        else:
            print(f"Was invited to {guild.name} ({guild.id})")

        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add):
                assert entry.target is not None
                assert self.bot.user is not None
                assert entry.user is not None
                if entry.target.id == self.bot.user.id:
                    print(f"  Invited by {entry.user.name} ({entry.user.id})")
                    break
        except Exception as e: # noqa: BLE001
            print("  Issue finding inviter, likely no audit log access. Caught as:", {e})

        if guild not in self.bot.authorized_guilds:
            channel = guild.system_channel
            
            if channel is None:
                for text_channel in guild.text_channels:
                    if text_channel.permissions_for(guild.me).send_messages:
                        channel = text_channel

            if channel:
                await channel.send("Oops! You're not allowed to invite me here!")
                print(f"  Sent not allowed message in channel {channel.name} ({channel.id})")
            else:
                print("  Couldn't find a channel to send a not allowed message in")

            await guild.leave()

async def setup(bot: tncbot.TNCBot):
    await bot.add_cog(Listen(bot))
