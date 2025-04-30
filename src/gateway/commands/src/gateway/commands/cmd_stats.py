# src/gateway/commands/cmd_stats.py

"""
Command module for handling the 'STATS' command. Shows basic mesh/gateway statistics.
"""

import logging

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
        node_count = len(server.mesh_interface.nodes)
        connection.notice(nick, f"Known Nodes: {node_count}")

        # 2. Gateway Node Info (if available)
        my_info = server.mesh_interface.getMyNodeInfo()
        my_id = my_info.get('user', {}).get('id', 'N/A')
        my_num = my_info.get('myNodeNum', 'N/A')
        connection.notice(nick, f"Gateway Node ID: {my_id} (Num: {my_num})")

        # 3. TODO: Add more stats if the Meshtastic API provides them easily
        # Examples (might require specific API calls or parsing metadata):
        # - Gateway uptime (would need to track start time in main.py)
        # - Channel utilization (if available in node metadata)
        # - Packets sent/received by gateway node (if available)
        # - Number of connected IRC clients
        irc_client_count = len(server.connections)
        connection.notice(nick, f"Connected IRC Clients: {irc_client_count}")


    except Exception as e:
        logging.error(f"Error retrieving stats: {e}", exc_info=True)
        connection.notice(nick, f"Error retrieving stats: {e}")
    connection.notice(nick, "--- End of Stats ---")

