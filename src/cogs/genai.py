import asyncio
import os
import random
import re
import time

import discord
import openai
import requests
from discord.ext import commands

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

# Время жизни кэша в секундах (600 сек = 10 минут).
# Поставь 0, если хочешь, чтобы бот качал документ заново на КАЖДЫЙ вопрос.
CACHE_TTL = 300

# Если авто-поиск вкладок пропустит какую-то вкладку, можешь вписать сюда её ID вручную (например "RUSSIA + REST": "t.xxxxx")
MANUAL_TAB_IDS: dict[str, str] = {
    # "IMPORTANT": "t.0",
    # "RUSSIA + REST": "",
}


def discover_and_fetch_all_tabs(doc_url: str) -> str:
    """
    Автоматически находит все вкладки (Tabs) в Google Документе и скачивает ВЕСЬ документ целиком в обход кэша Google.
    """
    match = re.search(r"(https://docs\.google\.com/document/d/[a-zA-Z0-9_-]+)", doc_url)
    if not match:
        print("[Lore Loader] Invalid Google Docs URL format!")
        return ""

    base_doc_url = match.group(1)
    # Добавляем timestamp (_cb), чтобы пробить серверный кэш Google Docs
    cache_buster = int(time.time())
    export_base_url = f"{base_doc_url}/export?format=txt&_cb={cache_buster}"
    edit_url = f"{base_doc_url}/edit?_cb={cache_buster}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    tab_ids: list[str] = ["t.0"]

    # 1. Добавляем вкладки, прописанные вручную (если есть)
    for manual_id in MANUAL_TAB_IDS.values():
        if manual_id and manual_id not in tab_ids:
            tab_ids.append(manual_id)

    # 2. Автоматически ищем все ID вкладок (t.xxxxxx) в HTML-коде страницы документа
    try:
        page_resp = requests.get(edit_url, headers=headers, timeout=15)
        if page_resp.ok:
            found_tabs = re.findall(r"\bt\.[a-zA-Z0-9_-]{6,20}\b", page_resp.text)
            for tid in found_tabs:
                if tid not in tab_ids:
                    tab_ids.append(tid)
    except requests.exceptions.RequestException as e:
        print("[Lore Loader] Could not scan /edit page for tab IDs:", e)

    print(f"[Lore Loader] Discovered tab IDs: {tab_ids}")

    # 3. Скачиваем каждую вкладку и склеиваем в один полный документ
    all_sections: list[str] = []
    seen_texts: set[int] = set()

    for idx, tab_id in enumerate(tab_ids, start=1):
        tab_export_url = f"{export_base_url}&tab={tab_id}"
        try:
            resp = requests.get(tab_export_url, headers=headers, timeout=15)
            if resp.ok:
                text = resp.text.strip()
                text_hash = hash(text)
                if text and text_hash not in seen_texts:
                    seen_texts.add(text_hash)
                    all_sections.append(f"=== DOCUMENT TAB {idx} ({tab_id}) ===\n{text}")
                    print(f"  + Loaded tab {tab_id}: {len(text)} chars")
        except requests.exceptions.RequestException as e:
            print(f"  - Failed to load tab {tab_id}: {e}")

    full_text = "\n\n".join(all_sections)
    print(f"[Lore Loader] TOTAL UNTRIMMED LORE SIZE: {len(full_text)} chars across {len(all_sections)} tab(s).")
    return full_text


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
        self.cached_lore: str = ""
        self.last_fetch_time: float = 0.0
        self.channel_memory: dict[int, tuple[str, str]] = {}

    async def get_full_lore(self, force: bool = False) -> str:
        """Возвращает полный лор из кэша или скачивает заново, если прошло больше CACHE_TTL секунд или force=True."""
        now = time.time()
        is_expired = (now - self.last_fetch_time) >= CACHE_TTL

        if force or not self.cached_lore or is_expired:
            url = os.getenv("TNCBOT_DOC_URL")
            if not url:
                return ""
            print(f"[Lore Loader] Fetching fresh document from Google Docs (force={force}, expired={is_expired})...")
            fresh_lore = await asyncio.to_thread(discover_and_fetch_all_tabs, url)
            if fresh_lore:
                self.cached_lore = fresh_lore
                self.last_fetch_time = time.time()
        else:
            remaining = int(CACHE_TTL - (now - self.last_fetch_time))
            print(f"[Lore Loader] Using cached lore ({len(self.cached_lore)} chars, expires in {remaining}s)")

        return self.cached_lore

    @commands.command()
    @check.is_verified_guild()
    @commands.has_permissions(administrator=True)
    async def reload_lore(self, ctx: commands.Context):
        """Команда для админов: принудительно перезагружает весь документ из Google Docs и очищает память диалога."""
        async with ctx.typing():
            lore = await self.get_full_lore(force=True)
            self.channel_memory.clear()
            await ctx.send(f"✅ Lore reloaded! Total untrimmed size: **{len(lore)}** characters.")

    async def _ask(self, ctx: commands.Context | discord.Interaction, full_text: str, prompt: str):
        assert ctx.guild is not None
        self.usage_exceeded = False
        aclient = self.bot.authorized_guilds[ctx.guild.id].genai

        channel_id = ctx.channel.id if ctx.channel else 0
        prev_prompt, prev_reply = self.channel_memory.get(channel_id, ("", ""))

        messages = [
            {"role": "system", "content": f"{PROMPT}\n\nFULL LORE DOCUMENT:\n{full_text}"}
        ]
        if prev_prompt and prev_reply:
            messages.append({"role": "user", "content": f"User asks: {prev_prompt}"})
            messages.append({"role": "assistant", "content": prev_reply[:1500]})
        messages.append({"role": "user", "content": f"User asks: {prompt}"})

        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                delay = RETRY_DELAY * (attempt - 1) + random.uniform(-0.5, 0.5)
                await asyncio.sleep(delay)
            try:
                selected_model = MODEL
                if attempt > RETRY_DOWNGRADE or self.usage_exceeded:
                    if attempt == RETRY_DOWNGRADE + 1 and not self.usage_exceeded:
                        await self.bot.send_message(
                            ctx,
                            "Model likely in high demand, switching to backup 1M-context model for further retries!"
                        )
                    selected_model = RETRY_DOWNGRADE_MODEL

                response = await aclient.chat.completions.create(
                    model=selected_model,
                    messages=messages,  # type: ignore
                    temperature=0.2,
                )

                if not response or not response.choices:
                    await self.bot.send_message(ctx, "Provider returned an empty response, retrying!")
                    continue

                reply_text = response.choices[0].message.content
                if reply_text:
                    reply_text = re.sub(r"<think>.*?</think>", "", reply_text, flags=re.DOTALL).strip()
                    self.channel_memory[channel_id] = (prompt, reply_text)

                    if len(reply_text) > MAX_LENGTH:
                        await self.bot.send_in_chunks(ctx, reply_text)
                    else:
                        await self.bot.send_message(ctx, reply_text)
                    return
                else:
                    await self.bot.send_message(
                        ctx,
                        "Failed to generate response in some sort of a way that didn't cause a crash, congrats!"
                    )
            except openai.InternalServerError as e:
                print(e.status_code, e.message)
                await self.bot.send_message(ctx, "Service error, model likely under high demand, retrying!")
            except (openai.RateLimitError, openai.APIStatusError) as e:
                print(e.status_code, e.message)
                self.usage_exceeded = True
                await self.bot.send_message(
                    ctx,
                    "Rate limit or status error on primary model, switching to backup 1M model!"
                )
            except Exception as e:  # noqa: BLE001
                print(type(e), e)
                await self.bot.send_message(ctx, "Encountered some sort of undefined error, oops!")

        await self.bot.send_message(ctx, f"Failed after {MAX_RETRIES} retries, aborting!")

    @commands.command()
    @check.is_verified_guild()
    @check.is_allowed_channel()
    @check.is_not_banned_user()
    async def ask(self, ctx: commands.Context, *, prompt: str):
        if ctx.guild is None:
            return
        text = await self.get_full_lore()
        if not text:
            await ctx.send("Failed to load lore document!")
            return

        print(f'{ctx.author.name} asks "{prompt}"')
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