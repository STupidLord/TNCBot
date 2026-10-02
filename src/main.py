import asyncio
import os

from dotenv import load_dotenv

import bot as tncbot
import command_register


async def main():
    load_dotenv(override=True)

    bot = tncbot.TNCBot()

    await command_register.register_commands(bot)

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user.name}") # type: ignore
        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} slash command(s) globally.")
        except Exception as e:  # noqa: BLE001
            print(f"Failed to sync commands: {e}")

    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    
    if not bot_token:
        return
    
    async with bot:
        await bot.start(bot_token)
    

if __name__ == "__main__":
    asyncio.run(main())
