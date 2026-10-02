import pathlib

import bot as tncbot


async def register_commands(bot: tncbot.TNCBot):
    commands_dir = pathlib.Path("./src/commands")
    for file in commands_dir.glob("*.py"):
        if file.name.startswith("_"): continue
        print(f"Loading commands from file {file}")
        extension_name = f"commands.{file.stem}"
        await bot.load_extension(extension_name)
