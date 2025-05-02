# src/gateway/commands/cmd_info.py

"""
Command module for handling the 'INFO' command. Displays detailed info about a node.
"""

import logging
import time # Added for formatting position timestamp

COMMAND_NAME = "INFO"
COMMAND_HELP = "INFO <node_id|shortname|nodenum> - Shows detailed info for a node"

def execute(server, connection, nick, args):
    """
    Executes the INFO command.

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
    # Find the node *number* first using the helper
    target_node_num = server._find_node_id(target_node_spec)

    if target_node_num is None:
         connection.notice(nick, f"Error: Could not find node matching '{target_node_spec}'.")
         return

    # Convert number back to string ID format used as key in nodes dict
    target_node_id_str = f"!{target_node_num:x}"
    connection.notice(nick, f"--- Info for Node {target_node_spec} ({target_node_id_str} / {target_node_num}) ---")

    try:
        # Attempt to get node details from the interface using the string ID
        # Note: This usually returns cached data. Fresh data might require other mechanisms.
        node_details = server.mesh_interface.nodes.get(target_node_id_str)

        if node_details:
            # Iterate through the top-level keys in the node details dictionary
            for key, value in node_details.items():
                 # Handle dictionaries by printing nested items or a summary
                 if isinstance(value, dict):
                      connection.notice(nick, f"  {key}:") # Indicate a dictionary section
                      # Print specific, known nested dictionaries cleanly
                      if key == 'user':
                           for ukey, uval in value.items(): connection.notice(nick, f"    user.{ukey}: {uval}")
                      elif key == 'position':
                           lat = value.get('latitude', 'N/A'); lon = value.get('longitude', 'N/A'); alt = value.get('altitude', 'N/A')
                           # Format position timestamp if available
                           pos_time_ts = value.get('time')
                           time_str = time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(pos_time_ts)) if pos_time_ts else 'N/A'
                           connection.notice(nick, f"    position: Lat {lat}, Lon {lon}, Alt {alt}m (Time: {time_str})")
                      elif key == 'deviceMetrics':
                           # Format device metrics nicely
                           batt = value.get('batteryLevel', 'N/A'); volt = value.get('voltage', 'N/A'); air = value.get('airUtilTx', 'N/A'); uptime = value.get('uptimeSeconds', 'N/A')
                           batt_str = f"{batt}%" if isinstance(batt, (int, float)) else 'N/A'
                           volt_str = f"{volt:.2f}V" if isinstance(volt, (int, float)) else 'N/A'
                           air_str = f"{air:.1f}%" if isinstance(air, (int, float)) else 'N/A'
                           uptime_str = f"{uptime}s" if isinstance(uptime, (int, float)) else 'N/A'
                           connection.notice(nick, f"    metrics: Batt {batt_str}, Volt {volt_str}, AirUtil {air_str}, Uptime {uptime_str}")
                      # Add more specific handlers for other complex dicts if needed
                      # e.g., 'loraConfig', 'channelSettings'
                      else:
                           # Generic handling for other dictionaries
                           dict_preview = str(value)[:100] + ('...' if len(str(value)) > 100 else '')
                           connection.notice(nick, f"    (Dict Data): {dict_preview}")
                 # Handle lists (e.g., channels) by summarizing or printing items
                 elif isinstance(value, list):
                      connection.notice(nick, f"  {key}: (List with {len(value)} items)")
                      # Optionally print first few items if list is small
                      # for i, item in enumerate(value[:3]): connection.notice(nick, f"    [{i}]: {item}")
                 # Print simple key-value pairs directly
                 else:
                      connection.notice(nick, f"  {key}: {value}")
        else:
            connection.notice(nick, "Could not retrieve details for this node (may be offline or data not available).")

    except AttributeError:
         logging.error("Could not access 'nodes' property on mesh_interface. Is it connected?")
         connection.notice(nick, "Error: Could not retrieve node list from Meshtastic interface.")
    except Exception as e:
        logging.error(f"Error retrieving node info for {target_node_id_str}: {e}", exc_info=True)
        connection.notice(nick, f"Error retrieving info: {e}")
    connection.notice(nick, "--- End of Info ---")


