import asyncio
import json
import os
import re
import shlex

import aiofiles
import aiosqlite
import discord
from discord import NotFound, guild
from discord.ext import commands
from google import genai
from tenacity import R

import help
from constants import CONFIG_FILE, DB_FILE, HEADER, MAX_LENGTH


class TNCBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=">", intents=intents, help_command=help.StyledHelp())
        self.config: dict = None # type: ignore
        self.ai: genai.Client() = None # type: ignore
        self.db: aiosqlite.Connection() = None # type: ignore
        self.authorized_guilds: list[guild.Guild] = None # type: ignore
        self.cli_running: bool = False

    @staticmethod
    def split_text_smart(text: str, header: str, limit: int) -> list[str]:
        """Splits text cleanly without severing words/sentences and ensures each piece begins with the header."""
        max_body_length = limit - len(header)
        words = text.split(' ')
        chunks = []
        current_chunk = []
        current_len = 0

        for word in words:
            added_len = len(word) + (1 if current_chunk else 0)
            if current_len + added_len > max_body_length:
                chunks.append(header + ' '.join(current_chunk))
                current_chunk = [word]
                current_len = len(word)
            else:
                current_chunk.append(word)
                current_len += added_len

        if current_chunk:
            chunks.append(header + ' '.join(current_chunk))

        return chunks

    @staticmethod
    async def send_in_chunks(ctx: commands.Context | discord.Interaction, text: str):
        """Splits response text cleanly and posts each piece to the Discord webhook."""
        chunks = TNCBot.split_text_smart(text, HEADER, MAX_LENGTH)
        for chunk in chunks:
            await TNCBot.send_message(ctx, chunk)

    @staticmethod
    async def send_message(ctx: commands.Context | discord.Interaction, message: str):
            if isinstance(ctx, commands.Context):
                await ctx.send(message)
            elif isinstance(ctx, discord.Interaction):
                await ctx.response.send_message(message)

    async def handle_cli_command(self, command: str):
        if command == "stop":
            self.cli_running = False
            await asyncio.sleep(0.1)
            await self.close()
        elif re.match(r"say", command):
            if len(command) < 4:
                print("say command seemingly too small to use")
                return
            
            info = command[4:]            
            channel_id, message = shlex.split(info)
            
            try:
                channel = self.get_channel(int(channel_id))
                if channel:
                    await channel.send(message) # type: ignore
                    print(f"Message sent in {channel.name}: {message}") # type: ignore
                else:
                    print("Channel not found")
            except Exception as e: # noqa: BLE001
                print(f"Error when trying to send message in channel: {type(e)} {e}")
        elif re.match(r"current-key", command):
            try:
                print(self.ai._api_client.api_key)
            except Exception as e: # noqa: BLE001
                print("Couldn't catch API key for reason:", e)
        else:
            print(f"Unknown command {command}")
    
    async def cli(self):
        await self.wait_until_ready()
        print("CLI input active")
        
        self.cli_running = True
        
        while self.cli_running:
            try:
                command = await asyncio.to_thread(input)

                if not self.cli_running:
                    break
                
                cleaned_command = command.strip()
                if not cleaned_command:
                    continue
                
                await self.handle_cli_command(cleaned_command)
            except (asyncio.CancelledError, RuntimeError):
                break
            except Exception as e:  # noqa: BLE001
                print(f"[CLI Error] Exception in CLI listener: {e}")
                await asyncio.sleep(1)

    async def setup_hook(self):
        print("Loading config")
        async with aiofiles.open(CONFIG_FILE, "r") as f:
            config_content = await f.read()
        if config_content:
            self.config = json.loads(config_content)
            print("Config loaded")
        else:
            print("Config failed to load")

        print("Activating CLI")
        self.loop.create_task(self.cli())
        print("CLI activated")

        print("Connecting to Google Gen AI")
        api_key = os.getenv("GEMINI_API_KEY")

        if api_key:
            self.ai = genai.Client(api_key=api_key)
            print("Google Gen AI connected")
        else:
            print("Google Gen AI failed to connect")

        print("Connecting to SQLite")
        self.db = await aiosqlite.connect(DB_FILE)
        await self.db.execute("PRAGMA journal_mode=WAL;")
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS allowed_channels (
                guild_id INTEGER,
                channel_id INTEGER,
                PRIMARY KEY (guild_id, channel_id)
            )
        """)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                guild_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await self.db.commit()
        print("SQLite connected")

        print("Loading authorized guilds")
        if self.config["authorized_guilds"]:
            authorized_guilds: list[guild.Guild] = []
            print("Authorized guilds loading:")
            for i in self.config["authorized_guilds"]:
                try:
                    _guild = await self.fetch_guild(i)
                    authorized_guilds.append(_guild)
                    print(f"  {i} | {_guild}")
                except NotFound:
                    print(f"  guild {i} does not exist or bot is not in it")
            self.authorized_guilds = authorized_guilds
            print("All authorized guilds loaded")
        else:
            print("No authorized guilds loaded")

    async def close(self):
        if self.ai:
            print("Closing Google Gen AI connection")
            self.ai.close()
            print("Google Gen AI connection closed")
        if self.db:
            print("Closing SQLite connection")
            await self.db.close()
        self.cli_running = False
        await super().close()
