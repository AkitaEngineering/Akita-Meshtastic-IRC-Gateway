"""TIME command."""

import datetime

COMMAND_NAME = "TIME"
COMMAND_HELP = "TIME - Shows the current timezone-aware server time"


def execute(server, connection, nick, args):
    if args:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return
    now = datetime.datetime.now().astimezone()
    connection.notice(nick, f"Server time: {now.isoformat(timespec='seconds')}")
