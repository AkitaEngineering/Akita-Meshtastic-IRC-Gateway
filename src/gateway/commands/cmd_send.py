"""SEND command."""

COMMAND_NAME = "SEND"
COMMAND_HELP = "SEND <message> - Sends a message to the configured mesh channel"


def execute(server, connection, nick, args):
    if not args:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return
    text = " ".join(args).strip()
    server.send_mesh_text(text)
    connection.notice(nick, f"Message queued for mesh channel {server.default_mesh_channel_index}.")
