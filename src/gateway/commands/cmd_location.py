"""LOCATION command."""

import time

COMMAND_NAME = "LOCATION"
COMMAND_HELP = "LOCATION - Shows the gateway node's reported GPS position"


def execute(server, connection, nick, args):
    if args:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return
    info = server.get_my_node_info()
    if not info:
        connection.notice(nick, "Gateway node information is not available.")
        return
    position = info.get("position", {})
    if not isinstance(position, dict):
        position = {}
    lat = position.get("latitude")
    lon = position.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        connection.notice(nick, "The gateway node has no valid GPS fix.")
        return
    connection.notice(nick, "--- Gateway Location ---")
    connection.notice(nick, f"Latitude: {lat:.5f}, Longitude: {lon:.5f}")
    altitude = position.get("altitude")
    if isinstance(altitude, (int, float)):
        connection.notice(nick, f"Altitude: {altitude} m")
    timestamp = position.get("time")
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        connection.notice(nick, f"Position time: {time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(timestamp))}")
    connection.notice(
        nick, f"Map: https://www.openstreetmap.org/?mlat={lat:.5f}&mlon={lon:.5f}#map=15/{lat:.5f}/{lon:.5f}"
    )
