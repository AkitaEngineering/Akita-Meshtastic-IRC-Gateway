"""STATS command."""

import datetime
import time

COMMAND_NAME = "STATS"
COMMAND_HELP = "STATS - Shows gateway and mesh statistics"


def execute(server, connection, nick, args):
    if args:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return
    nodes = server.nodes_snapshot()
    my_info = server.get_my_node_info() or {}
    user = my_info.get("user", {})
    node_id = user.get("id", "N/A") if isinstance(user, dict) else "N/A"
    node_num = my_info.get("num", "N/A")
    uptime = datetime.timedelta(seconds=int(time.monotonic() - server.started_at))
    connection.notice(nick, "--- Gateway & Mesh Statistics ---")
    connection.notice(nick, f"Known nodes: {len(nodes)}")
    connection.notice(nick, f"Gateway node: {node_id} (Num: {node_num})")
    connection.notice(nick, f"Gateway uptime: {uptime}")
    connection.notice(nick, f"Connected IRC clients: {len(server.connections)}")
    connection.notice(
        nick,
        f"IRC users in control channel: {len(server.channels.get(server.control_channel_name).clients) if server.channels.get(server.control_channel_name) else 0}",
    )
    connection.notice(nick, "--- End of Statistics ---")
