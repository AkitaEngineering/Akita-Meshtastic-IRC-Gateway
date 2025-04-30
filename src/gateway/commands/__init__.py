# src/gateway/commands/__init__.py

"""
Commands package for the Akita Meshtastic IRC Gateway (AMIG).

This file makes the 'commands' directory a Python package.
Command modules (cmd_*.py) within this directory will be dynamically loaded
by the main application script (main.py).

Each command module should define:
- COMMAND_NAME (str): The keyword users type to trigger the command (case-insensitive).
- COMMAND_HELP (str): A short description shown by the HELP command.
- execute(server, connection, nick, args): A function that implements the command logic.
    - server: The MeshtasticGatewayServer instance.
    - connection: The IRC connection object for the client.
    - nick: The nickname of the user issuing the command.
    - args: A list of strings representing the arguments provided after the command name.
"""

# This file can remain empty. Its presence signifies that the directory
# 'commands' should be treated as a package.

