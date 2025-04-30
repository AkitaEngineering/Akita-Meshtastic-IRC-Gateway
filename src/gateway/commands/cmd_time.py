# src/gateway/commands/cmd_time.py

"""
Command module for handling the 'TIME' command. Shows server time.
"""

import logging
import datetime

COMMAND_NAME = "TIME"
COMMAND_HELP = "TIME - Shows the current server date and time"

def execute(server, connection, nick, args):
    """
    Executes the TIME command.

    Args:
        server: The MeshtasticGatewayServer instance.
        connection: The IRC connection object for the client.
        nick: The nickname of the user issuing the command.
        args: A list of strings (should be empty).
    """
    try:
        # Get current local time on the server
        now = datetime.datetime.now()
        # Format with timezone information if possible (may depend on OS/locale)
        formatted_time = now.strftime('%Y-%m-%d %H:%M:%S %Z%z')
        connection.notice(nick, f"Server time: {formatted_time}")
    except Exception as e:
        logging.error(f"Error getting server time: {e}", exc_info=True)
        connection.notice(nick, "Error retrieving server time.")

