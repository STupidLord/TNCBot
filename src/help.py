from typing import Any, Optional

import discord
from discord.ext import commands
from discord.ext.commands import Command, Group


class StyledHelp(commands.HelpCommand):
    def __init__(self):
        super().__init__()

    # Taken from original help to make some formatting better
    def get_command_signature(self, command: Command[Any, ..., Any], /) -> str:
        """Retrieves the signature portion of the help page.

        .. versionchanged:: 2.0

            ``command`` parameter is now positional-only.

        Parameters
        ------------
        command: :class:`Command`
            The command to get the signature of.

        Returns
        --------
        :class:`str`
            The signature for the command.
        """
        parent: Optional[Group[Any, ..., Any]] = command.parent  # type: ignore # noqa: UP045
        entries = []
        while parent is not None:
            if not parent.signature or parent.invoke_without_command:
                entries.append(parent.name)
            else:
                entries.append(parent.name + ' ' + parent.signature)
            parent = parent.parent  # type: ignore
        parent_sig = ' '.join(reversed(entries))

        if len(command.aliases) > 0:
            aliases = '|'.join(command.aliases)
            fmt = f'[{command.name}|{aliases}]'
            if parent_sig:
                fmt = parent_sig + ' ' + fmt
            alias = fmt
        else:
            alias = command.name if not parent_sig else parent_sig + ' ' + command.name

        if command.signature == '':
            return f'{self.context.clean_prefix}{alias}'
        else:
            return f'{self.context.clean_prefix}{alias} {command.signature}'

    # 1. Main Help Menu (!help)
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            # This works, it feels wrong, but it works
            title=f"{self.context.bot.user.name}", # type: ignore
            description=f"Use `{self.context.bot.command_prefix}help <command>` for more info.",
            color=discord.Color.dark_purple()
        )

        for cog, commands_list in mapping.items():
            filtered_cmds = await self.filter_commands(commands_list, sort=True)
            if not filtered_cmds:
                continue
 
            cog_name = cog.qualified_name if cog else "General"
            cmd_names = [f"`{c.name}`" for c in filtered_cmds]

            embed.add_field(
                name=f"{cog_name}", 
                value=", ".join(cmd_names), 
                inline=False
            )

        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        try:
            can_run = await command.can_run(self.context)
        except commands.CommandError:
            can_run = False

        # 2. If they lack permissions, deny the help message
        if not can_run:
            embed = discord.Embed(
                title="Error",
                description="You do not have permission to use or view help for this command.",
                color=discord.Color.brand_red()
            )
            await self.get_destination().send(embed=embed)
            return

        embed = discord.Embed(
            title=f"Command: {command.name}",
            description=command.help or "No description provided.",
            color=discord.Color.brand_green()
        )

        embed.add_field(
            name="Usage Blueprint", 
            value=f"`{self.get_command_signature(command)}`", 
            inline=False
        )

        if command.description:
            embed.add_field(
                name="Argument Parameters", 
                value=f"```\n{command.description}\n```", 
                inline=False
            )

        if command.aliases:
            embed.add_field(
                name="Aliases", 
                value=", ".join([f"`{a}`" for a in command.aliases]), 
                inline=False
            )

        await self.get_destination().send(embed=embed)

    async def send_error_message(self, error):
        embed = discord.Embed(
            title="Error",
            description=error,
            color=discord.Color.brand_red()
        )

        await self.get_destination().send(embed=embed)
