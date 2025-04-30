# src/gateway/commands/cmd_ping.py

"""
Command module for handling the 'PING' command. Sends a Meshtastic ping request.
"""

import logging

COMMAND_NAME = "PING"
COMMAND_HELP = "PING <node_id|shortname> - Sends a Meshtastic ping request to a node"

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
    target_node_id = server._find_node_id(target_node_spec) # Use server's helper

    if not target_node_id:
         connection.notice(nick, f"Error: Could not find node matching '{target_node_spec}'.")
         return

    connection.notice(nick, f"Sending Meshtastic Ping to {target_node_spec} ({target_node_id})...")
    try:
        # Call the sendPing method on the interface
        # Note: The real API might return immediately; the response (pong)
        # comes asynchronously via pubsub event handled in server.py.
        success = server.mesh_interface.sendPing(destinationId=target_node_id)

        # Provide feedback based on the immediate return value (useful for mock/errors)
        if success:
             connection.notice(nick, f"Ping request sent to {target_node_spec}. Waiting for reply...")
        else:
             # This might indicate the interface couldn't even attempt to send
             connection.notice(nick, f"Failed to send ping request (node unknown to interface?).")

    except AttributeError:
         logging.error("Meshtastic interface does not support sendPing (might be older version or mock limitation).")
         connection.notice(nick, "Error: This Meshtastic interface does not support the PING command.")
    except Exception as e:
        logging.error(f"Failed to send ping via Meshtastic: {e}", exc_info=True)
        connection.notice(nick, f"Error sending ping: {e}")

