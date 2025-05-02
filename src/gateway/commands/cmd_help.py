# src/gateway/commands/cmd_help.py

"""
Command module for handling the 'HELP' command. Lists available commands.
"""

import logging

COMMAND_NAME = "HELP"
COMMAND_HELP = "HELP [command] - Shows available commands or help for a specific command"

def execute(server, connection, nick, args):
    """
    Executes the HELP command. Lists all commands or shows help for one.

    Args:
        server: The MeshtasticGatewayServer instance.
        connection: The IRC connection object for the client.
        nick: The nickname of the user issuing the command.
        args: A list containing an optional command name to get help for.
    """
    if not args:
        # List all available commands
        connection.notice(nick, "*** Available Commands (Type HELP <command> for details):")
        if hasattr(server, 'commands') and server.commands:
            # Sort commands alphabetically for clarity
            sorted_commands = sorted(server.commands.items())
            command_list = []
            for name, cmd_info in sorted_commands:
                # Just list the command names for the general help
                command_list.append(name)
            # Send commands possibly in multiple lines if list is long
            max_line_len = 400 # Approx max length for IRC lines before wrapping/truncation
            current_line = ""
            for cmd in command_list:
                if not current_line:
                    current_line = cmd
                elif len(current_line) + len(cmd) + 2 < max_line_len: # +2 for ", "
                    current_line += f", {cmd}"
                else:
                    # Send the current line if adding the next command would exceed length
                    connection.notice(nick, current_line)
                    current_line = cmd # Start a new line
            if current_line: # Send the last line if it has content
                 connection.notice(nick, current_line)

        else:
            connection.notice(nick, "(No commands seem to be registered)")
    else:
        # Show help for a specific command
        target_command = args[0].upper()
        if hasattr(server, 'commands') and target_command in server.commands:
            # Retrieve the specific help text stored during registration
            help_text = server.commands[target_command].get('help', f"{target_command} - (No help text provided)")
            connection.notice(nick, f"Help for {target_command}: {help_text}")
        else:
            connection.notice(nick, f"Unknown command: '{args[0]}'. Type HELP for a list.")

