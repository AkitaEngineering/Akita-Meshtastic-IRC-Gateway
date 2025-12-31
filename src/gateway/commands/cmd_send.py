# src/gateway/commands/cmd_send.py

"""
Command module for handling the 'SEND' command. Sends a message to the default mesh channel.
"""

import logging

# Attempt to import meshtastic errors for specific handling
try:
    from meshtastic import MeshtasticError, Timeout as MeshtasticTimeout
except ImportError:
    # Define dummy exceptions if library not present
    class MeshtasticError(Exception): pass
    class MeshtasticTimeout(Exception): pass

COMMAND_NAME = "SEND"
COMMAND_HELP = "SEND <message> - Sends message to default mesh channel"

def execute(server, connection, nick, args):
    """
    Executes the SEND command.

    Args:
        server: The MeshtasticGatewayServer instance.
        connection: The IRC connection object for the client.
        nick: The nickname of the user issuing the command.
        args: A list of strings (message parts).
    """
    if not args:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return

    text_to_send = " ".join(args)
    
    # Validate message length (Meshtastic has limits)
    if len(text_to_send) > 240:
        connection.notice(nick, f"Error: Message too long ({len(text_to_send)} chars). Maximum is 240 characters.")
        return
    
    if not text_to_send.strip():
        connection.notice(nick, "Error: Message cannot be empty.")
        return
    
    channel_index = server.default_mesh_channel_index
    connection.notice(nick, f"Sending '{text_to_send}' to mesh channel {channel_index}...")
    try:
        # Use the server's Meshtastic interface instance to send the text
        server.mesh_interface.sendText(text_to_send, channelIndex=channel_index)
        # Confirmation is generally handled by receiving the message back if loopback is on,
        # or potentially via specific ACK mechanisms if implemented for broadcast.
        # We don't typically wait here for broadcast confirmation.
        connection.notice(nick, f"Message sent to mesh channel {channel_index}.")

    except MeshtasticTimeout:
        logging.warning(f"Meshtastic timeout sending message for {nick}.")
        connection.notice(nick, f"Error: Timeout sending message via mesh.")
    except MeshtasticError as me:
        logging.error(f"Meshtastic error sending message for {nick}: {me}", exc_info=True)
        connection.notice(nick, f"Meshtastic Error sending message: {me}")
    except Exception as e:
        logging.error(f"Unexpected error sending message for {nick}: {e}", exc_info=True)
        connection.notice(nick, f"Error sending message: {e}")

