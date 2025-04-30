# src/gateway/commands/cmd_alarm.py

"""
Command module for handling the 'ALARM' command. Broadcasts an alarm message.
"""

import logging

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
    # Prepend "ALARM:" to the message for easy identification on the mesh
    full_message = f"ALARM: {alarm_text}"
    channel_index = server.default_mesh_channel_index

    connection.notice(nick, f"Broadcasting Alarm to mesh channel {channel_index}: '{alarm_text}'...")
    try:
        # Send the prefixed message to the default channel
        server.mesh_interface.sendText(full_message, channelIndex=channel_index)
    except Exception as e:
        logging.error(f"Failed to send alarm via Meshtastic: {e}", exc_info=True)
        connection.notice(nick, f"Error sending alarm: {e}")

