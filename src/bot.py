import asyncio
import json
import os
import re
import shlex

import aiosqlite
import discord
from discord import NotFound
from discord.ext import commands
from google import genai

import help
from constants import HEADER, MAX_LENGTH, STORAGE


class AuthorizedGuild:
    def __init__(self, guild: discord.Guild, api_key: genai.Client):
        self.guild = guild
        self.genai = api_key

class TNCBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=">", intents=intents, help_command=help.StyledHelp())
        self.db: aiosqlite.Connection() = None # type: ignore
        self.authorized_guilds: dict[int, AuthorizedGuild] = {}
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
        elif re.match(r"key", command):
            if len(command) < 4:
                print("say command seemingly too small to use")
                return

            guild_id = command[4:]

            try:
                print(self.authorized_guilds[int(guild_id)].genai._api_client.api_key)
            except Exception as e: # noqa: BLE001
                print("Couldn't catch API key for reason:", type(e))
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
        print("Connecting to SQLite")
        self.db = await aiosqlite.connect(STORAGE / "bot.db")
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
        authorized_guilds_str = os.getenv("TNCBOT_AUTHORIZED_GUILDS", r"{}")
        authorized_guilds = json.loads(authorized_guilds_str)
        if authorized_guilds:
            print("Authorized guilds loading:")
            for id, api_key in authorized_guilds.items():
                try:
                    print("  " + id)
                    print("    Fetching Discord guild")
                    _guild = await self.fetch_guild(int(id))
                    print("    Fetching Google GenAI client")
                    _genai = genai.Client(api_key=api_key)
                    _auth_guild = AuthorizedGuild(_guild, _genai)
                    self.authorized_guilds[int(id)] = _auth_guild
                    print(f"    Loaded authorized guild {_guild.name} | {api_key}")
                except NotFound:
                    print("    Guild does not exist or bot is not in it")
            print("All authorized guilds loaded")
        else:
            print("No authorized guilds loaded")

        # Keep this at the end smh
        print("Activating CLI")
        self.loop.create_task(self.cli())

    async def close(self):
        if self.authorized_guilds:
            for o in self.authorized_guilds.values():
                print(f"Closing Google GenAI connection for {o.guild.name} ({o.guild.id})")
                o.genai.close()
                print("Closed")
        if self.db:
            print("Closing SQLite connection")
            await self.db.close()
        self.cli_running = False
        await super().close()
