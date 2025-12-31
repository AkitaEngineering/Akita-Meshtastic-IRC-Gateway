# src/gateway/commands/cmd_dm.py

"""
Command module for handling the 'DM' command. Sends a direct message to a specific node.
"""

import logging

# Attempt to import meshtastic errors for specific handling
try:
    from meshtastic import MeshtasticError, Timeout as MeshtasticTimeout
except ImportError:
    # Define dummy exceptions if library not present
    class MeshtasticError(Exception): pass
    class MeshtasticTimeout(Exception): pass

COMMAND_NAME = "DM"
COMMAND_HELP = "DM <node_id|shortname|nodenum> <message> - Sends direct message to a node"

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
    
    # Validate message length
    if len(text_to_send) > 240:
        connection.notice(nick, f"Error: Message too long ({len(text_to_send)} chars). Maximum is 240 characters.")
        return
    
    if not text_to_send.strip():
        connection.notice(nick, "Error: Message cannot be empty.")
        return

    # Use the server's helper method to find the node ID (string)
    target_node_id = server._find_node_id(target_node_spec)

    if target_node_id is None: # Check if None was returned
         connection.notice(nick, f"Error: Could not find node matching '{target_node_spec}'. Use NODES command.")
         return

    # Use node ID for destinationId (Meshtastic API accepts both ID strings and node numbers)
    destination_id = target_node_id
    connection.notice(nick, f"Sending DM '{text_to_send}' to {target_node_spec} ({destination_id})...")

    try:
        # Request ACK for Direct Messages
        # sendText returns immediately in real library, ACK comes via pubsub
        server.mesh_interface.sendText(
            text=text_to_send,
            destinationId=destination_id,
            wantAck=True
        )
        connection.notice(nick, f"DM request sent to {target_node_spec}. Waiting for ACK/NAK...")
        # Note: Actual confirmation (ACK/NAK) will be displayed when the
        # corresponding pubsub message is received by server.py's handlers

    except MeshtasticTimeout:
        logging.warning(f"Meshtastic timeout sending DM to {destination_id} for {nick}.")
        connection.notice(nick, f"Error: Timeout sending DM to {target_node_spec}.")
    except MeshtasticError as me:
        logging.error(f"Meshtastic error sending DM to {destination_id} for {nick}: {me}", exc_info=True)
        connection.notice(nick, f"Meshtastic Error sending DM: {me}")
    except Exception as e:
        logging.error(f"Unexpected error sending DM to {destination_id} for {nick}: {e}", exc_info=True)
        connection.notice(nick, f"Error sending DM: {e}")

