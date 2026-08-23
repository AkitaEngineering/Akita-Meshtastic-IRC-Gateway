"""ALARM command."""

COMMAND_NAME = "ALARM"
COMMAND_HELP = "ALARM <message> - Broadcasts a high-priority Meshtastic alert"


def execute(server, connection, nick, args):
    if not args:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return
    text = " ".join(args).strip()
    server.send_mesh_alert(text)
    connection.notice(nick, f"Alert queued for mesh channel {server.default_mesh_channel_index}.")
