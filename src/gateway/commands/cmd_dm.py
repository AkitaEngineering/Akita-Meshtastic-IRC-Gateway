"""DM command."""

from collections.abc import Mapping

COMMAND_NAME = "DM"
COMMAND_HELP = "DM <node_id|shortname|nodenum> <message> - Sends a reliable direct message"


def execute(server, connection, nick, args):
    if len(args) < 2:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return
    target_spec = args[0]
    destination_id = server._find_node_id(target_spec)
    if destination_id is None:
        connection.notice(nick, f"Node '{target_spec}' was not found. Use NODES to list known nodes.")
        return
    text = " ".join(args[1:]).strip()

    def on_ack(packet):
        if not connection.connected:
            return
        decoded = packet.get("decoded", {}) if isinstance(packet, Mapping) else {}
        routing = decoded.get("routing", {}) if isinstance(decoded, Mapping) else {}
        reason = routing.get("errorReason", "NONE") if isinstance(routing, Mapping) else "UNKNOWN"
        if reason == "NONE":
            connection.notice(nick, f"DM to {target_spec} acknowledged.")
        else:
            connection.notice(nick, f"DM to {target_spec} failed: {reason}.")

    packet = server.send_mesh_text(text, destination_id, on_ack)
    packet_id = server.packet_id(packet)
    suffix = f" (packet {packet_id})" if packet_id is not None else ""
    connection.notice(nick, f"DM queued for {target_spec}{suffix}; awaiting ACK/NAK.")
