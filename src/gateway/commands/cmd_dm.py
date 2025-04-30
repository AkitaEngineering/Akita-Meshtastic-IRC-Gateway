# src/gateway/commands/cmd_dm.py

"""
Command module for handling the 'DM' command. Sends a direct message to a specific node.
"""

import logging

COMMAND_NAME = "DM"
COMMAND_HELP = "DM <node_id|shortname> <message> - Sends direct message to a node"

def execute(server, connection, nick, args):
    """
    Executes the DM command.

    Args:
        server: The MeshtasticGatewayServer instance.
        connection: The IRC connection object for the client.
        nick: The nickname of the user issuing the command.
        args: A list of strings (node specifier followed by message parts).
    """
    if len(args) < 2:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return

    target_node_spec = args[0]
    text_to_send = " ".join(args[1:])

    # Use the server's helper method to find the node ID
    target_node_id = server._find_node_id(target_node_spec)

    if not target_node_id:
         connection.notice(nick, f"Error: Could not find node matching '{target_node_spec}'. Use NODES command.")
         return

    connection.notice(nick, f"Sending DM '{text_to_send}' to {target_node_spec} ({target_node_id})...")
    try:
        # Request ACK for Direct Messages
        ack = server.mesh_interface.sendText(text_to_send, destinationId=target_node_id, wantAck=True)
        # Note: Real ACK confirmation comes via pubsub event handled in server.py
        if ack and isinstance(server.mesh_interface, server.MockMeshtasticInterface):
             # Provide immediate feedback only for mock interface's direct return
             connection.notice(nick, f"DM sent to {target_node_spec}. (Simulated ACK received)")
        elif not ack and isinstance(server.mesh_interface, server.MockMeshtasticInterface):
             connection.notice(nick, f"DM sent to {target_node_spec}. (Simulated ACK *not* received)")

    except Exception as e:
        logging.error(f"Failed to send DM via Meshtastic: {e}", exc_info=True)
        connection.notice(nick, f"Error sending DM: {e}")

