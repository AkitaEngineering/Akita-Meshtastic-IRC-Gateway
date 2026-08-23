"""PING command using Meshtastic's REPLY_APP echo service."""

import time
from collections.abc import Mapping

COMMAND_NAME = "PING"
COMMAND_HELP = "PING <node_id|shortname|nodenum> - Requests an echo reply from a node"


def execute(server, connection, nick, args):
    if len(args) != 1:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return
    target_spec = args[0]
    destination_id = server._find_node_id(target_spec)
    if destination_id is None:
        connection.notice(nick, f"Node '{target_spec}' was not found. Use NODES to list known nodes.")
        return
    started = time.monotonic()

    def on_response(packet):
        if not connection.connected:
            return
        decoded = packet.get("decoded", {}) if isinstance(packet, Mapping) else {}
        portnum = decoded.get("portnum") if isinstance(decoded, Mapping) else None
        elapsed_ms = (time.monotonic() - started) * 1000
        if portnum == "REPLY_APP":
            connection.notice(nick, f"PONG from {target_spec} in {elapsed_ms:.0f} ms.")
            return
        routing = decoded.get("routing", {}) if isinstance(decoded, Mapping) else {}
        reason = routing.get("errorReason", "NO_RESPONSE") if isinstance(routing, Mapping) else "NO_RESPONSE"
        connection.notice(nick, f"Ping to {target_spec} failed: {reason}.")

    packet = server.send_mesh_ping(destination_id, on_response)
    packet_id = server.packet_id(packet)
    suffix = f" (packet {packet_id})" if packet_id is not None else ""
    connection.notice(nick, f"Ping queued for {target_spec}{suffix}.")
