import asyncio
import os

import discord
from dotenv import load_dotenv

import bot as tncbot
import register


async def main():
    load_dotenv(override=True)

    bot = tncbot.TNCBot()

    await register.register_cogs(bot)

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user.name}") # type: ignore
        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} slash command(s) globally.")
        except Exception as e:  # noqa: BLE001
            print(f"Failed to sync commands: {e}")
        print("Setting status")
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.custom,
                name="custom",
                state=">help"
            )
        )

    bot_token = os.getenv("TNCBOT_TOKEN")
    
    if not bot_token:
        return
    
    async with bot:
        await bot.start(bot_token)
    

if __name__ == "__main__":
    asyncio.run(main())
