"""INFO command."""

import datetime
import time

COMMAND_NAME = "INFO"
COMMAND_HELP = "INFO <node_id|shortname|nodenum> - Shows detailed cached node information"


def _value(value, suffix=""):
    return f"{value}{suffix}" if isinstance(value, (int, float)) else "N/A"


def execute(server, connection, nick, args):
    if len(args) != 1:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return
    target = server._find_node_id(args[0])
    if target is None:
        connection.notice(nick, f"Node '{args[0]}' was not found. Use NODES to list known nodes.")
        return
    node = server.nodes_snapshot().get(target, {})
    user = node.get("user", {}) if isinstance(node.get("user"), dict) else {}
    metrics = node.get("deviceMetrics", {}) if isinstance(node.get("deviceMetrics"), dict) else {}
    position = node.get("position", {}) if isinstance(node.get("position"), dict) else {}
    connection.notice(nick, f"--- Node {target} ---")
    connection.notice(nick, f"Name: {user.get('longName', 'N/A')} ({user.get('shortName', 'N/A')})")
    connection.notice(
        nick,
        f"Number: {node.get('num', 'N/A')} | Hardware: {user.get('hwModel', 'N/A')} | Role: {user.get('role', 'N/A')}",
    )
    last_heard = node.get("lastHeard")
    heard = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(last_heard)) if last_heard else "Never"
    connection.notice(
        nick, f"Last heard: {heard} | SNR: {_value(node.get('snr'), ' dB')} | Hops: {node.get('hopsAway', 'N/A')}"
    )
    connection.notice(
        nick,
        f"Battery: {_value(metrics.get('batteryLevel'), '%')} | Voltage: {_value(metrics.get('voltage'), ' V')} | "
        f"Channel use: {_value(metrics.get('channelUtilization'), '%')} | Air TX: {_value(metrics.get('airUtilTx'), '%')}",
    )
    uptime = metrics.get("uptimeSeconds")
    if isinstance(uptime, (int, float)):
        connection.notice(nick, f"Node uptime: {datetime.timedelta(seconds=int(uptime))}")
    lat, lon = position.get("latitude"), position.get("longitude")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        connection.notice(nick, f"Position: {lat:.5f}, {lon:.5f}; altitude {_value(position.get('altitude'), ' m')}")
    connection.notice(nick, "--- End of Node Info ---")
