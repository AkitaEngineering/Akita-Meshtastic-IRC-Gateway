# src/gateway/commands/cmd_alarm.py

"""
Command module for handling the 'ALARM' command. Broadcasts an alarm message.
"""

import logging

# Attempt to import meshtastic errors for specific handling
try:
    from meshtastic import MeshtasticError, Timeout as MeshtasticTimeout
except ImportError:
    # Define dummy exceptions if library not present
    class MeshtasticError(Exception): pass
    class MeshtasticTimeout(Exception): pass

COMMAND_NAME = "ALARM"
COMMAND_HELP = "ALARM <message> - Broadcasts an ALARM message to the default mesh channel"

def execute(server, connection, nick, args):
    """
    Executes the ALARM command.

    Args:
        server: The MeshtasticGatewayServer instance.
        connection: The IRC connection object for the client.
        nick: The nickname of the user issuing the command.
        args: A list of strings (alarm message parts).
    """
    if not args:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return

    alarm_text = " ".join(args)
    
    # Validate message length (leave room for "ALARM: " prefix)
    if len(alarm_text) > 230:
        connection.notice(nick, f"Error: Alarm message too long ({len(alarm_text)} chars). Maximum is 230 characters.")
        return
    
    if not alarm_text.strip():
        connection.notice(nick, "Error: Alarm message cannot be empty.")
        return
    
    # Prepend "ALARM:" to the message for easy identification on the mesh
    full_message = f"ALARM: {alarm_text}"
    channel_index = server.default_mesh_channel_index

    connection.notice(nick, f"Broadcasting Alarm to mesh channel {channel_index}: '{alarm_text}'...")
    try:
        # Send the prefixed message to the default channel
        server.mesh_interface.sendText(full_message, channelIndex=channel_index)
        connection.notice(nick, f"Alarm message sent to mesh channel {channel_index}.")

    except MeshtasticTimeout:
        logging.warning(f"Meshtastic timeout sending ALARM for {nick}.")
        connection.notice(nick, f"Error: Timeout sending ALARM via mesh.")
    except MeshtasticError as me:
        logging.error(f"Meshtastic error sending ALARM for {nick}: {me}", exc_info=True)
        connection.notice(nick, f"Meshtastic Error sending ALARM: {me}")
    except Exception as e:
        logging.error(f"Unexpected error sending ALARM for {nick}: {e}", exc_info=True)
        connection.notice(nick, f"Error sending ALARM: {e}")

