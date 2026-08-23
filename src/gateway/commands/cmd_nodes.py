"""NODES command."""

import time

COMMAND_NAME = "NODES"
COMMAND_HELP = "NODES - Lists nodes currently known to the gateway"


def execute(server, connection, nick, args):
    if args:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return
    nodes = server.nodes_snapshot()
    connection.notice(nick, f"--- Meshtastic Nodes ({len(nodes)}) ---")
    if not nodes:
        connection.notice(nick, "No nodes are currently known.")
        return
    ordered = sorted(nodes.items(), key=lambda item: item[1].get("lastHeard", 0) or 0, reverse=True)
    for node_id, node in ordered:
        user = node.get("user", {})
        long_name = user.get("longName", "N/A") if isinstance(user, dict) else "N/A"
        short_name = user.get("shortName", "N/A") if isinstance(user, dict) else "N/A"
        last_heard = node.get("lastHeard")
        heard = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(last_heard)) if last_heard else "Never"
        snr = node.get("snr")
        snr_text = f"{snr:.1f} dB" if isinstance(snr, (int, float)) else "N/A"
        connection.notice(
            nick,
            f"Num: {node.get('num', 'N/A')} | ID: {node_id} | Name: {long_name} ({short_name}) | "
            f"SNR: {snr_text} | Last heard: {heard}",
        )
    connection.notice(nick, "--- End of Node List ---")
