# src/gateway/commands/cmd_ping.py

"""
Command module for handling the 'PING' command. Sends a Meshtastic ping request.
"""

import logging

# Attempt to import meshtastic errors for specific handling
try:
    from meshtastic import MeshtasticError, Timeout as MeshtasticTimeout
except ImportError:
    # Define dummy exceptions if library not present
    class MeshtasticError(Exception): pass
    class MeshtasticTimeout(Exception): pass


COMMAND_NAME = "PING"
COMMAND_HELP = "PING <node_id|shortname|nodenum> - Sends a Meshtastic ping request to a node"

def execute(server, connection, nick, args):
    """
    Executes the PING command.

    Args:
        server: The MeshtasticGatewayServer instance.
        connection: The IRC connection object for the client.
        nick: The nickname of the user issuing the command.
        args: A list containing the node specifier.
    """
    if not args:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return

    target_node_spec = args[0]
    # Find the node ID (string)
    target_node_id = server._find_node_id(target_node_spec)

    if target_node_id is None:
         connection.notice(nick, f"Error: Could not find node matching '{target_node_spec}'.")
         return

    # Use node ID for destinationId (Meshtastic API accepts both ID strings and node numbers)
    destination_id = target_node_id
    connection.notice(nick, f"Sending Meshtastic Ping to {target_node_spec} ({destination_id})...")

    try:
        # Call the sendPing method on the interface using the node number
        # sendPing returns immediately, PONG comes via pubsub
        server.mesh_interface.sendPing(destinationId=destination_id)
        connection.notice(nick, f"Ping request sent to {target_node_spec}. Waiting for reply (PONG)...")
        # Note: Actual PONG confirmation will be displayed when the
        # corresponding pubsub message is received by server.py's handlers

    except AttributeError:
         # Handle cases where sendPing might not be implemented
         logging.error("Meshtastic interface does not support sendPing.")
         connection.notice(nick, "Error: This Meshtastic interface does not support the PING command.")
    except MeshtasticTimeout:
        logging.warning(f"Meshtastic timeout sending PING to {destination_id} for {nick}.")
        connection.notice(nick, f"Error: Timeout sending PING to {target_node_spec}.")
    except MeshtasticError as me:
        logging.error(f"Meshtastic error sending PING to {destination_id} for {nick}: {me}", exc_info=True)
        connection.notice(nick, f"Meshtastic Error sending PING: {me}")
    except Exception as e:
        logging.error(f"Unexpected error sending PING to {destination_id} for {nick}: {e}", exc_info=True)
        connection.notice(nick, f"Error sending PING: {e}")

