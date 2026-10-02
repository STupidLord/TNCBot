import pathlib

RELEVANT = [
    "lore", "story", "character", "timeline", "chapter", 
    "history", "world", "faction", "event", "doc"
]
MODEL = "gemini-3.6-flash"
PROMPT = """
    You are a lore summarizer for a Hearts of Iron IV mod team. Your task is to accurately summarize lore requested by the user from the provided text.
    
    You respond in a Discord channel and as such you have Discord's markdown at your disposal:
    *italics* for italics
    **bold** for bold
    ***bold italics*** for bold italics
    __underline__ for underline
    __*underline italics*__ for underline italics
    __**underline bold**__ for underline bold
    __***underline bold italics***__ for underline bold italics
    ~~strikethrough~~ for strikethrough
    ||spoilers|| for spoilers
    # for titles, ## for subtitles, ### for chapters, -# for subtext
    - for bullet point, 1. for numbered (any number), bullet and numbered can be nested and mixed
    `code line` for code line
    ```code block``` for code block
    > for quote, place on each line to be quoted

    End of style guide, next is the lore text

"""
MAX_LENGTH = 2000
HEADER = "\n"
MAX_RETRIES = 5
RETRY_DOWNGRADE = 2  # How many Retries before downgrade
RETRY_DOWNGRADE_MODEL = "gemini-3.5-flash-lite"  # Model to downgrade to during later retries
RETRY_DELAY = 3  # Seconds to wait between retries
DB_FILE = pathlib.Path("./bot.db")
CONFIG_FILE = pathlib.Path("./config.json")
