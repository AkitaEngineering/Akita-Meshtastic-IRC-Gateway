# src/gateway/commands/cmd_nodes.py

"""
Command module for handling the 'NODES' command. Lists known Meshtastic nodes.
"""

import logging
import time

COMMAND_NAME = "NODES"
COMMAND_HELP = "NODES - Lists known nodes on the mesh"

def execute(server, connection, nick, args):
    """
    Executes the NODES command.

    Args:
        server: The MeshtasticGatewayServer instance.
        connection: The IRC connection object for the client.
        nick: The nickname of the user issuing the command.
        args: A list of strings (should be empty for this command).
    """
    connection.notice(nick, "--- Meshtastic Nodes ---")
    try:
        # Access the nodes dictionary/property from the interface
        nodes = server.mesh_interface.nodes
        if not nodes:
            connection.notice(nick, "No nodes currently known to the gateway.")
            return

        # Sort nodes by lastHeard time (most recent first), handle nodes without lastHeard
        # items() gives pairs of (node_id_str, node_info_dict)
        sorted_nodes = sorted(nodes.items(), key=lambda item: item[1].get('lastHeard', 0), reverse=True)

        for node_id_str, node_info in sorted_nodes:
            user_data = node_info.get('user', {})
            node_num = node_info.get('num', 'N/A') # Get node number if available
            long_name = user_data.get('longName', 'N/A')
            short_name = user_data.get('shortName', 'N/A')
            last_heard_ts = node_info.get('lastHeard')
            # Format timestamp nicely, handle case where lastHeard is missing or zero
            last_heard_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_heard_ts)) if last_heard_ts else 'Never'
            snr = node_info.get('snr', 'N/A') # Check for 'snr' or potentially 'rxSnr' if source varies
            # Format SNR to one decimal place if it's a number
            try:
                snr_str = f"{float(snr):.1f}" if isinstance(snr, (int, float)) else 'N/A'
            except (ValueError, TypeError):
                snr_str = 'N/A'

            # Construct the info line for each node
            info_line = f"Num: {node_num} | ID: {node_id_str} | Name: {long_name} ({short_name}) | SNR: {snr_str} | LastHeard: {last_heard_str}"
            connection.notice(nick, info_line)

    except AttributeError:
         logging.error("Could not access 'nodes' property on mesh_interface. Is it connected?")
         connection.notice(nick, "Error: Could not retrieve node list from Meshtastic interface.")
    except Exception as e:
        logging.error(f"Error retrieving Meshtastic nodes: {e}", exc_info=True)
        connection.notice(nick, f"Error retrieving nodes: {e}")
    connection.notice(nick, "--- End of Node List ---")

