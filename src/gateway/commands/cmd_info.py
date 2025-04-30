# src/gateway/commands/cmd_info.py

"""
Command module for handling the 'INFO' command. Displays detailed info about a node.
"""

import logging

COMMAND_NAME = "INFO"
COMMAND_HELP = "INFO <node_id|shortname> - Shows detailed info for a node"

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
    target_node_id = server._find_node_id(target_node_spec) # Use server's helper

    if not target_node_id:
         connection.notice(nick, f"Error: Could not find node matching '{target_node_spec}'.")
         return

    connection.notice(nick, f"--- Info for Node {target_node_spec} ({target_node_id}) ---")
    try:
        # Attempt to get node details from the interface
        # Note: getNode might just return cached data. For fresh data,
        # the real API might need requestConfig=True or similar,
        # which could involve delays or specific pubsub responses.
        node_details = server.mesh_interface.getNode(target_node_id)

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
                           time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(value.get('time', 0))) if value.get('time') else 'N/A'
                           connection.notice(nick, f"    position: Lat {lat}, Lon {lon}, Alt {alt}m (Time: {time_str})")
                      elif key == 'deviceMetrics':
                           batt = value.get('batteryLevel', 'N/A'); volt = value.get('voltage', 'N/A'); air = value.get('airUtilTx', 'N/A'); uptime = value.get('uptimeSeconds', 'N/A')
                           connection.notice(nick, f"    metrics: Batt {batt}%, Volt {volt:.2f}V, AirUtil {air:.1f}%, Uptime {uptime}s")
                      # Add more specific handlers for other complex dicts if needed
                      # else:
                      #      connection.notice(nick, f"    (Dictionary - use specific commands or check logs for full data)")
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

    except Exception as e:
        logging.error(f"Error retrieving node info for {target_node_id}: {e}", exc_info=True)
        connection.notice(nick, f"Error retrieving info: {e}")
    connection.notice(nick, "--- End of Info ---")

