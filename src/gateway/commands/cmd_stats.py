# src/gateway/commands/cmd_stats.py

"""
Command module for handling the 'STATS' command. Shows basic mesh/gateway statistics.
"""

import logging
import time # For uptime calculation
import datetime # For formatting timedelta

# Track server start time (can be set in main.py or imported)
# A simple approach is to grab it when the module loads, assuming main starts soon after.
# A more robust method would pass the start time from main.py.
try:
    # Try importing from main if it's structured to expose start time
    # from gateway.main import SERVER_START_TIME # Example, needs adjustment in main.py
    SERVER_START_TIME = time.time() # Fallback: Use module load time
except ImportError:
    SERVER_START_TIME = time.time() # Fallback if main cannot be imported this way


COMMAND_NAME = "STATS"
COMMAND_HELP = "STATS - Shows basic mesh and gateway statistics"

def execute(server, connection, nick, args):
    """
    Executes the STATS command.

    Args:
        server: The MeshtasticGatewayServer instance.
        connection: The IRC connection object for the client.
        nick: The nickname of the user issuing the command.
        args: A list of strings (should be empty).
    """
    connection.notice(nick, "--- Gateway & Mesh Statistics ---")
    try:
        # 1. Node Count
        node_count = 0
        if hasattr(server.mesh_interface, 'nodes') and server.mesh_interface.nodes is not None:
             node_count = len(server.mesh_interface.nodes)
        connection.notice(nick, f"Known Nodes: {node_count}")

        # 2. Gateway Node Info (if available)
        my_info = None
        if hasattr(server.mesh_interface, 'getMyNodeInfo'):
             my_info = server.mesh_interface.getMyNodeInfo()

        if my_info:
            my_id = my_info.get('user', {}).get('id', 'N/A')
            my_num = my_info.get('myNodeNum', 'N/A')
            connection.notice(nick, f"Gateway Node ID: {my_id} (Num: {my_num})")
        else:
            connection.notice(nick, "Gateway Node Info: N/A (Interface not fully initialized?)")


        # 3. Gateway Uptime
        uptime_seconds = int(time.time() - SERVER_START_TIME)
        uptime_str = str(datetime.timedelta(seconds=uptime_seconds)) # Format as H:MM:SS
        connection.notice(nick, f"Gateway Uptime: {uptime_str}")

        # 4. Connected IRC Clients
        irc_client_count = len(server.connections)
        connection.notice(nick, f"Connected IRC Clients: {irc_client_count}")

        # TODO: Add more stats if the Meshtastic API provides them easily
        # Examples (might require specific API calls or parsing metadata):
        # - Channel utilization (if available in node metadata)
        # - Packets sent/received by gateway node (if available)

    except Exception as e:
        logging.error(f"Error retrieving stats: {e}", exc_info=True)
        connection.notice(nick, f"Error retrieving stats: {e}")
    connection.notice(nick, "--- End of Stats ---")

