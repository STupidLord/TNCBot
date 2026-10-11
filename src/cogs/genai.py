import asyncio
import os
import random
import re

import discord
import requests
from discord.ext import commands
from google.genai import errors, types

import bot as tncbot
import check
from constants import (
    MAX_LENGTH,
    MAX_RETRIES,
    MODEL,
    PROMPT,
    RELEVANT,
    RETRY_DELAY,
    RETRY_DOWNGRADE,
    RETRY_DOWNGRADE_MODEL,
)


def get_doc_text(doc_url: str) -> str:
    """Fetches plain text or HTML directly from the published Google Doc link."""
    if re.search(r"/export$", doc_url):
        doc_url = doc_url.replace("/export", "/export?format=txt")
    elif not re.search(r"/export\?format=txt$", doc_url):
        return ""

    try:
        response = requests.get(doc_url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print("Something went wrong:", e)
        return ""

def is_relevant(text: str, input: str) -> bool:
    """Checks if prompt meets relevancy check"""
    if any(keyword in input.lower() for keyword in RELEVANT):
        return True

    words = [w.strip("?,.!\"'") for w in input.lower().split() if len(w) > 3]

    return bool(any(word in words for word in text.lower()))

class GenAI(commands.Cog):
    def __init__(self, bot):
        self.bot: tncbot.TNCBot = bot
        self.usage_exceeded: bool = False

    async def _ask(self, ctx: commands.Context | discord.Interaction, text: str, prompt: str):
        assert ctx.guild is not None
        lore_prompt = f"{PROMPT}\n{text}\nUser asks: {prompt}"
        self.usage_exceeded = False
        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                delay = RETRY_DELAY * (attempt - 1) + random.uniform(-0.5, 0.5)
                await asyncio.sleep(delay)
            try:
                async with self.bot.authorized_guilds[ctx.guild.id].genai.aio as aclient:
                    selected_model = MODEL
                    if attempt > RETRY_DOWNGRADE or self.usage_exceeded:
                        if attempt == RETRY_DOWNGRADE + 1:
                            await self.bot.send_message(ctx, "Model likely in high demand, downgrading to lite model for further retries!")
                        selected_model = RETRY_DOWNGRADE_MODEL
                    response = await aclient.models.generate_content(
                        model = selected_model,
                        contents = lore_prompt,
                        config=types.GenerateContentConfig(
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True) # type: ignore
                        ),
                    )
                    if response.text:
                        if len(response.text) > MAX_LENGTH:
                            await self.bot.send_in_chunks(ctx, response.text)
                        else:
                            await self.bot.send_message(ctx, response.text)
                        return
                    else:
                        await self.bot.send_message(ctx, "Failed to regenerate response in some sort of a way that didn't cause a crash, congrats!")
            except errors.ServerError as e:
                print(e.details.get("error").get("code"), e.details.get("error").get("message")) # type: ignore
                await self.bot.send_message(ctx, "Service error, model likely under high demand, retrying!")
            except errors.ClientError as e:
                print(e.details.get("error").get("code"), e.details.get("error").get("message")) # type: ignore
                self.usage_exceeded = True
                await self.bot.send_message(ctx, "Client error, daily allowance likely exceeded, retrying with lite model!")
            except Exception as e:  # noqa: BLE001
                print(type(e), e)
                await self.bot.send_message(ctx, "Encountered some sort of undefined error, oops!")
        await self.bot.send_message(ctx, f"Failed after {MAX_RETRIES} retries, aborting!")

    @commands.command()
    @check.is_verified_guild()
    @check.is_allowed_channel()
    @check.is_not_banned_user()
    async def ask(self, ctx: commands.Context, *, prompt: str):
        if ctx.guild is None: return
        url = os.getenv("TNCBOT_DOC_URL")
        if url is None: return
        text = get_doc_text(url)
        if text == "":
            return
        else:
            print(f"{ctx.author.name} asks \"{prompt}\"")
            async with ctx.typing():
                await self._ask(ctx, text, prompt)

    @ask.error
    async def ask_error(self, ctx: commands.Context, error):
        if isinstance(error, check.UnAllowedChannelError):
            await ctx.send("That command is not allowed in this channel!")
        elif isinstance(error, check.BannedUserError):
            await ctx.send("Not allowed to use this command!")
        elif isinstance(error, check.UnverifiedGuildError):
            await ctx.send("This server is unverified!")


async def setup(bot: tncbot.TNCBot):
    await bot.add_cog(GenAI(bot))
