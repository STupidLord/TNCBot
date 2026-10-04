import pathlib

import bot as tncbot


async def register_cogs(bot: tncbot.TNCBot):
    cogs_dir = pathlib.Path("./src/cogs")
    for file in cogs_dir.glob("*.py"):
        if file.name.startswith("_"): continue
        print(f"Loading Cog from file {file}")
        extension_name = f"cogs.{file.stem}"
        await bot.load_extension(extension_name)
