# src/gateway/commands/cmd_location.py

"""
Command module for handling the 'LOCATION' command. Shows gateway node's location.
"""

import logging
import time

COMMAND_NAME = "LOCATION"
COMMAND_HELP = "LOCATION - Shows the gateway node's GPS location (if available)"

def execute(server, connection, nick, args):
    """
    Executes the LOCATION command.

    Args:
        server: The MeshtasticGatewayServer instance.
        connection: The IRC connection object for the client.
        nick: The nickname of the user issuing the command.
        args: A list of strings (should be empty).
    """
    connection.notice(nick, "--- Gateway Location ---")
    try:
        # Get information about the gateway's own node
        my_info = server.mesh_interface.getMyNodeInfo()
        if not my_info:
             connection.notice(nick, "Error: Could not retrieve gateway node info.")
             return

        pos = my_info.get('position', {}) # Position data is usually nested

        # Extract latitude, longitude, altitude, and time from position data
        lat = pos.get('latitude')
        lon = pos.get('longitude')
        alt = pos.get('altitude')
        pos_time_ts = pos.get('time') # Position timestamp (seconds since epoch)

        # Check if essential latitude and longitude are present
        if lat is not None and lon is not None:
            # Format coordinates to a reasonable number of decimal places
            connection.notice(nick, f"Latitude: {lat:.5f}, Longitude: {lon:.5f}")
            # Show altitude if available
            if alt is not None:
                connection.notice(nick, f"Altitude: {alt} m")
            # Show position timestamp if available
            if pos_time_ts:
                 # Format timestamp using local timezone settings
                 pos_time_str = time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(pos_time_ts))
                 connection.notice(nick, f"Position Time: {pos_time_str}")

            # Provide a link to a map (e.g., Google Maps, OpenStreetMap)
            connection.notice(nick, f"Map Link (approx): https://www.google.com/maps?q={lat},{lon}")
            # connection.notice(nick, f"Map Link (OSM): https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}")
        else:
            # Message if location data is missing or incomplete
            connection.notice(nick, "Location data not available or incomplete for the gateway node.")
            connection.notice(nick, "(Node needs a GPS fix and position sharing enabled).")

    except AttributeError:
         logging.error("Could not call getMyNodeInfo on mesh_interface. Is it connected?")
         connection.notice(nick, "Error: Could not retrieve gateway node info from Meshtastic interface.")
    except Exception as e:
        logging.error(f"Error retrieving location: {e}", exc_info=True)
        connection.notice(nick, f"Error retrieving location: {e}")
    connection.notice(nick, "--- End of Location ---")

