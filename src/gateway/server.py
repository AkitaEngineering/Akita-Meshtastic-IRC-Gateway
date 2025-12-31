# src/gateway/server.py

"""
Core IRC Server and Meshtastic interaction logic for the Gateway.
Refactored for modular command handling.
"""

import sys
import logging
import time
import datetime
import threading
import shlex
from typing import Optional, Dict, Any, Callable, List, Tuple
from collections.abc import Mapping

import irc.server
import irc.client
import irc.strings

# --- Configuration Constants ---
# These might be moved to a config module later
IRC_SERVER_HOST = "0.0.0.0"
IRC_SERVER_PORT = 6667
IRC_SERVER_NAME = "meshtastic.gw" # Default name, can be overridden by args
CONTROL_CHANNEL = "#meshtastic-ctrl" # Default control channel
DEFAULT_MESH_CHANNEL_INDEX = 0 # Default mesh channel for SEND/ALARM

# --- Mock Meshtastic Interface (Keep as is or move to separate file) ---
class MockMeshtasticInterface:
    """
    A placeholder class to simulate Meshtastic interactions.
    Includes mock location and ping. Used if no real interface is configured.
    """
    def __init__(self) -> None:
        self._nodes_data: Dict[str, Dict[str, Any]] = {
            "!MOCKNODE1": {"user": {"id": "!MOCKNODE1", "longName": "Mock Node 1", "shortName": "MK1"}, "lastHeard": int(time.time()) - 60, "snr": 10.0, "position": {}, "num": 1},
            "!MOCKNODE2": {"user": {"id": "!MOCKNODE2", "longName": "Mock Node 2", "shortName": "MK2"}, "lastHeard": int(time.time()) - 120, "snr": -5.5, "position": {}, "num": 2},
            "!MYNODEID": {"user": {"id": "!MYNODEID", "longName": "My Gateway Node", "shortName": "GW"}, "lastHeard": int(time.time()), "snr": 0.0, "position": {'latitude': 42.886, 'longitude': -79.249, 'altitude': 180}, "num": 12345678},
        }
        self._on_receive_callback: Optional[Callable[[Dict[str, Any], Any], None]] = None
        self._lock = threading.Lock()  # Thread safety for node data access
        self.my_node_num = 12345678
        self.my_node_id = "!MYNODEID"
        logging.info("Initialized Mock Meshtastic Interface")
        threading.Thread(target=self._simulate_incoming_messages, daemon=True).start()
        threading.Thread(target=self._simulate_node_updates, daemon=True).start()

    def sendText(self, text: str, channelIndex: int = 0, destinationId: Optional[str] = None, wantAck: bool = False) -> bool:
        """Simulates sending a text message."""
        if not text or not isinstance(text, str):
            logging.warning("[Mock Meshtastic] Invalid text message provided")
            return False
        
        # Sanitize text length (Meshtastic has message length limits)
        if len(text) > 240:  # Typical Meshtastic message limit
            logging.warning(f"[Mock Meshtastic] Message truncated from {len(text)} to 240 characters")
            text = text[:240]
        
        ack = False
        with self._lock:
            if destinationId:
                logging.info(f"[Mock Meshtastic] Sending DM '{text}' to {destinationId} (wantAck={wantAck})")
                if wantAck and destinationId in self._nodes_data:
                     ack = True
                     logging.info(f"[Mock Meshtastic] Simulating ACK received for DM to {destinationId}")
            else:
                logging.info(f"[Mock Meshtastic] Sending to channel {channelIndex}: '{text}'")
        # Mock returns simulated ACK status directly
        return ack

    def sendPing(self, destinationId: str, payload: bytes = b'ping') -> bool:
        """Simulates sending a ping request."""
        if not destinationId:
            logging.warning("[Mock Meshtastic] Invalid destination ID for ping")
            return False
        
        logging.info(f"[Mock Meshtastic] Sending Ping to {destinationId}")
        with self._lock:
            if destinationId in self._nodes_data:
                logging.info(f"[Mock Meshtastic] Simulating PONG received from {destinationId}")
                # Simulate receiving a pong packet after a short delay
                threading.Timer(1.5, self._simulate_pong, args=[destinationId]).start()
                return True # Simulate success sending ping
            else:
                logging.warning(f"[Mock Meshtastic] Cannot send Ping, node {destinationId} unknown.")
                return False # Simulate failure sending ping

    def getMyNodeInfo(self) -> Dict[str, Any]:
        """Simulates getting local node info."""
        with self._lock:
            my_info = self._nodes_data.get(self.my_node_id, {}).copy()
            my_info['myNodeNum'] = self.my_node_num
            return my_info

    def getNode(self, nodeId: str, request_config: bool = False) -> Optional[Dict[str, Any]]:
        """Simulates getting info for a specific node."""
        with self._lock:
            node_data = self._nodes_data.get(nodeId)
            return node_data.copy() if node_data else None

    @property
    def nodes(self) -> Dict[str, Dict[str, Any]]:
         """Simulates accessing the node database (nodes property)."""
         with self._lock:
             return self._nodes_data.copy()

    def subscribe_on_receive(self, callback: Callable[[Dict[str, Any], Any], None]) -> None:
        """Allows the IRC server to register a callback for received messages."""
        if not callable(callback):
            raise TypeError("Callback must be callable")
        self._on_receive_callback = callback
        logging.info("[Mock Meshtastic] Registered receive callback.")

    def _simulate_incoming_messages(self) -> None:
        """Internal method to simulate messages arriving from the mesh."""
        msg_counter = 0
        while True:
            time.sleep(45) # Simulate message arrival interval
            msg_counter += 1
            sender_node_id = "!MOCKNODE1"
            with self._lock:
                sender_node_info = self._nodes_data.get(sender_node_id)
            sender_name = sender_node_info.get('user', {}).get('shortName', sender_node_id) if sender_node_info else sender_node_id
            message_text = f"Simulated mesh message #{msg_counter}."
            channel_index = 0
            logging.info(f"[Mock Meshtastic] Simulating incoming: '{message_text}' from {sender_name} ({sender_node_id}) on ch {channel_index}")

            if self._on_receive_callback:
                # Construct a packet similar to what meshtastic pubsub provides
                mock_packet = {
                    'from': sender_node_id, 'to': '^all', # Indicate broadcast
                    'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'text': message_text},
                    'channel': channel_index, 'rxTime': int(time.time()),
                    'rssi': -70 + msg_counter, 'snr': 8.5 - msg_counter*0.5, 'hopLimit': 3,
                }
                try:
                    # Call the registered callback (server's on_meshtastic_receive)
                    self._on_receive_callback(mock_packet, self)
                except Exception as e:
                    logging.error(f"Error in Meshtastic receive callback: {e}", exc_info=True)

    def _simulate_node_updates(self) -> None:
        """Simulate nodes appearing/disappearing or updating."""
        time.sleep(60) # Wait a bit before simulating update
        new_node_id = "!NEWNODE3"
        logging.info(f"[Mock Meshtastic] Simulating new node appearing: {new_node_id}")
        with self._lock:
            self._nodes_data[new_node_id] = {"user": {"id": new_node_id, "longName": "Newly Seen Node", "shortName": "NEW"}, "lastHeard": int(time.time()), "snr": 5.0, "position": {}, "num": 3}
        # In a real implementation using pubsub, this would trigger a node update event.
        # pub.sendMessage("meshtastic.node.updated", node=self._nodes_data[new_node_id], interface=self)

    def _simulate_pong(self, from_node_id: str) -> None:
        """Internal method to simulate receiving a PONG reply."""
        if self._on_receive_callback:
            logging.info(f"[Mock Meshtastic] Simulating PONG packet from {from_node_id}")
            mock_packet = {
                'from': from_node_id, 'to': self.my_node_num, # Pong is directed back
                'decoded': {'portnum': 'PING_APP', 'payload': b'pong_payload'}, # Example payload
                'channel': 0, # Pongs might not have a channel concept like text
                'rxTime': int(time.time()),
                'rssi': -65, 'snr': 9.0,
            }
            try:
                self._on_receive_callback(mock_packet, self)
            except Exception as e:
                logging.error(f"Error simulating PONG callback: {e}", exc_info=True)

# --- IRC Gateway Server Class ---
class MeshtasticGatewayServer(irc.server.SimpleIRCServer):
    """
    Minimal IRC Server acting as a command gateway to Meshtastic.
    Uses a command registry for modular command handling.
    """
    def __init__(
        self,
        mesh_interface_ref: Any,
        control_channel_name: str,
        default_mesh_channel_index: int,
        *args: Any,
        **kwargs: Any
    ) -> None:
        """
        Initializes the IRC server instance.

        Args:
            mesh_interface_ref: An initialized Meshtastic interface instance (real or mock).
            control_channel_name (str): The name of the IRC channel for commands.
            default_mesh_channel_index (int): The default Meshtastic channel index.
            *args, **kwargs: Arguments passed to the base SimpleIRCServer.
        """
        super().__init__(*args, **kwargs)
        self.mesh_interface = mesh_interface_ref
        self.control_channel_name = control_channel_name
        self.default_mesh_channel_index = default_mesh_channel_index
        self.commands: Dict[str, Dict[str, Any]] = {} # Command registry: {'CMD_NAME': {'execute': func, 'help': str}}
        logging.info(f"MeshtasticGatewayServer initialized. Control Channel: {self.control_channel_name}")

        # Subscribe to Meshtastic messages (PubSub setup moved to main.py for real interface)
        # If using mock interface, set up its direct callback here.
        if hasattr(self.mesh_interface, 'subscribe_on_receive'): # Check if mock interface
             self.mesh_interface.subscribe_on_receive(self.on_meshtastic_receive)

    def register_command(self, command_name: str, execute_func: Callable, help_text: str) -> None:
        """Registers a command handler discovered by main.py."""
        if not command_name or not isinstance(command_name, str):
            raise ValueError("Command name must be a non-empty string")
        if not callable(execute_func):
            raise TypeError("Execute function must be callable")
        if not help_text or not isinstance(help_text, str):
            raise ValueError("Help text must be a non-empty string")
        
        upper_name = command_name.upper()
        if upper_name in self.commands:
            logging.warning(f"Command '{upper_name}' is already registered. Overwriting.")
        self.commands[upper_name] = {'execute': execute_func, 'help': help_text}
        logging.debug(f"Registered command: {upper_name}")

    def _send_server_message_to_control_channel(self, message: str, prefix: str = "[GW]") -> None:
        """Helper to send a message FROM THE SERVER to all users in the control channel."""
        if not message:
            return
        
        # Sanitize message to prevent IRC injection
        message = message.replace('\r', '').replace('\n', ' ')
        if len(message) > 400:  # IRC message length limit
            message = message[:397] + "..."
        
        full_message = f"{prefix} {message}"
        logging.debug(f"Sending server message to control channel {self.control_channel_name}: {full_message}")
        # Construct the source mask for messages originating from the server itself
        source_mask = f"{self.servername}!{self.servername}@{self.servername}"
        # Format the raw IRC line for a PRIVMSG
        raw_line = f":{source_mask} PRIVMSG {self.control_channel_name} :{full_message}"

        # Iterate through all currently connected clients
        for conn in self.connections:
             # Check if the connection object is still valid and connected
             if conn and conn.connected:
                 try:
                     # Send the raw IRC line to the client
                     conn.send_line(raw_line)
                 except Exception as e:
                     # Log errors if sending fails (e.g., client disconnected abruptly)
                     logging.error(f"Error sending message to connection {conn.nickname}: {e}")

    def get_node_name(self, node_id: str) -> str:
        """Helper to get a display name for a node ID using the mesh interface."""
        if not node_id:
            return "UNKNOWN"
        
        try:
            node_info = self.mesh_interface.getNode(node_id)
            if node_info and node_info.get('user'):
                # Prefer short name, then long name, then fall back to node ID
                user_info = node_info.get('user', {})
                return user_info.get('shortName') or user_info.get('longName') or node_id
        except Exception as e:
            logging.warning(f"Error getting node info for {node_id}: {e}")
        # Fallback if info retrieval fails or node not found
        return node_id

    # --- Meshtastic Event Handling ---
    def on_meshtastic_receive(self, packet, interface=None):
        """
        Callback function triggered by Meshtastic message reception (via pubsub or mock).
        Parses the packet and relays relevant information to the IRC control channel.

        Args:
            packet (dict): The decoded packet dictionary from the Meshtastic library.
            interface: The Meshtastic interface instance (passed by pubsub, may not always be present).
        """
        try:
            logging.debug(f"Received Meshtastic packet: {packet}")
            portnum = packet.get('decoded', {}).get('portnum', 'UNKNOWN')
            sender_id = packet.get('from', 'UNKNOWN_SENDER')
            sender_name = self.get_node_name(sender_id) # Get friendly name
            rssi = packet.get('rssi', 'N/A')
            snr = packet.get('snr', 'N/A')

            # Handle Text Messages
            if portnum == 'TEXT_MESSAGE_APP' and 'text' in packet.get('decoded', {}):
                message_text = packet['decoded']['text']
                channel_index = packet.get('channel', '?')
                is_direct = packet.get('to', '') != '^all'

                prefix = f"[MESH Rx ch{channel_index} RSSI:{rssi} SNR:{snr}]"
                if is_direct:
                    recipient_id = packet.get('to', 'UNKNOWN_RECIPIENT')
                    # Check if the DM is addressed to this gateway node
                    my_info = self.mesh_interface.getMyNodeInfo()
                    my_num = my_info.get('myNodeNum')
                    my_id_str = my_info.get('user',{}).get('id')
                    # Compare recipient ID with gateway's node number and node ID string
                    if str(recipient_id) == str(my_num) or recipient_id == my_id_str:
                         self._send_server_message_to_control_channel(f"DM From <{sender_name}>: {message_text}", prefix=prefix)
                    else:
                         # Log DMs not intended for the gateway if needed for debugging
                         logging.debug(f"Ignoring DM from {sender_name} to {recipient_id}")
                else:
                    # Broadcast message received on a channel
                    self._send_server_message_to_control_channel(f"<{sender_name}> {message_text}", prefix=prefix)

            # Handle Pong Replies (Example using PING_APP portnum)
            elif portnum == 'PING_APP': # Note: Real portnum might differ
                 # Payload might contain round trip time or other data
                 payload = packet.get('decoded',{}).get('payload')
                 # Format payload for display (assuming bytes)
                 payload_str = repr(payload) if payload else "N/A"
                 self._send_server_message_to_control_channel(f"PONG reply from <{sender_name}> RSSI:{rssi} SNR:{snr} Payload:{payload_str}", prefix="[PING]")

            # TODO: Handle other relevant packet types (e.g., POSITION_APP, NODEINFO_APP)
            # elif portnum == 'POSITION_APP':
            #    lat = packet.get('decoded', {}).get('latitude')
            #    lon = packet.get('decoded', {}).get('longitude')
            #    alt = packet.get('decoded', {}).get('altitude')
            #    if lat is not None and lon is not None:
            #         self._send_server_message_to_control_channel(f"Position from <{sender_name}>: Lat {lat:.5f}, Lon {lon:.5f}, Alt {alt}m", prefix="[POS]")

        except Exception as e:
            # Log exceptions during packet processing
            logging.exception(f"Error processing received Meshtastic packet: {e}")
            # Notify IRC users about the error
            self._send_server_message_to_control_channel(f"Error processing mesh packet: {e}", prefix="[GW ERROR]")

    # --- Overriding IRC Server Methods ---
    def on_connect(self, connection):
        """Called by the IRC library when a new client connects."""
        super().on_connect(connection) # Call base class method
        logging.info(f"Client connected: {connection.realhost}")
        # Send welcome messages (NOTICE is often preferred for server messages)
        connection.notice(connection.nickname, f"*** Welcome to the Akita Meshtastic IRC Gateway (AMIG) ({self.servername})")
        connection.notice(connection.nickname, f"*** Join {self.control_channel_name} to interact with the mesh.")
        connection.notice(connection.nickname, "*** Type HELP in the channel for commands.")

    def on_join(self, connection, event):
        """Called by the IRC library when a client attempts to join a channel."""
        channel = event.target
        nick = connection.nickname
        # Allow joining only the designated control channel (case-insensitive comparison)
        if irc.strings.lower(channel) == irc.strings.lower(self.control_channel_name):
            logging.info(f"{nick} joined control channel {channel}")
            # Manually construct and send the JOIN message back to the client
            # (SimpleIRCServer doesn't handle this automatically)
            source = f"{nick}!{connection.user}@{connection.host}"
            connection.send_line(f":{source} JOIN :{channel}")
            # Send channel topic (RPL_TOPIC 332)
            connection.topic(channel, f"Akita Meshtastic IRC Gateway (AMIG) | Type HELP for commands")
            # Send NAMES list (RPL_NAMREPLY 353, RPL_ENDOFNAMES 366)
            # TODO: Implement proper tracking of users in the channel for accurate NAMES list
            # For now, just send the joining user
            connection.names(channel, [nick])
            connection.notice(nick, f"*** Joined {channel}. Type HELP for commands or chat normally.")
        else:
            # Reject attempts to join other channels
            logging.warning(f"{nick} tried to join invalid channel {channel}")
            # Send standard IRC error numeric (e.g., 403 No Such Channel)
            connection.error(f"403 {nick} {channel} :Cannot join channel - only {self.control_channel_name} is allowed.")

    def on_privmsg(self, connection: Any, event: Any) -> None:
        """Called by the IRC library when a PRIVMSG is received (channel msg or query)."""
        target = event.target # The channel or nickname the message was sent to
        message = event.arguments[0] if event.arguments else "" # The actual message text
        source_nick = connection.nickname # Nickname of the sender

        # Validate and sanitize input
        if not message or not isinstance(message, str):
            return
        
        # Sanitize message length
        if len(message) > 512:  # IRC message limit
            message = message[:512]
        
        # Remove control characters that could be used for IRC injection
        message = ''.join(char for char in message if ord(char) >= 32 or char in '\r\n')

        logging.debug(f"IRC PRIVMSG: From={source_nick}, To={target}, Msg={message}")

        # Process only messages directed to the control channel
        if irc.strings.lower(target) == irc.strings.lower(self.control_channel_name):
            is_command = False
            command_word = ""
            args: List[str] = []
            if message:
                # Basic check if the first word matches a registered command
                parts = message.split(None, 1)
                command_word = parts[0].upper()
                if command_word in self.commands: # Check against the command registry
                    is_command = True
                    if len(parts) > 1:
                         # Use shlex to parse arguments, handling quotes etc.
                         try:
                             args = shlex.split(parts[1])
                         except ValueError as e:
                             # Handle potential errors during argument parsing (e.g., unmatched quotes)
                             logging.warning(f"Argument parsing error for '{parts[1]}' from {source_nick}: {e}")
                             connection.notice(source_nick, f"Error parsing arguments: {e}")
                             return # Stop processing if arguments are invalid

            if is_command:
                # If it's a known command, delegate to the command handler
                self.handle_control_command(connection, source_nick, command_word, args)
            else:
                # If it's not a command, treat it as a chat message and relay it
                logging.debug(f"Relaying chat message from {source_nick} in {target}")
                # Construct the source mask for the originating user
                source_mask = f"{source_nick}!{connection.user}@{connection.host}"
                # Format the raw IRC line to send to other clients
                raw_line = f":{source_mask} PRIVMSG {target} :{message}"
                # Send to all other connected clients in the channel
                for conn in self.connections:
                    # Don't send the message back to the original sender
                    # Check if the recipient connection is still active
                    # TODO: Add check if 'conn' is actually in the control channel
                    if conn != connection and conn.connected:
                        try:
                            conn.send_line(raw_line)
                        except Exception as e:
                            logging.error(f"Error relaying message to connection {conn.nickname}: {e}")

        elif target == self.servername:
             # Handle private messages sent directly to the server/gateway name
             connection.notice(source_nick, "Please send commands inside the control channel.")
        else:
            # Ignore private messages sent between users or to other non-existent channels
            logging.debug(f"Ignoring PRIVMSG not directed to control channel or server: {target}")

    # --- Command Handling Logic ---
    def _find_node_id(self, node_spec: str) -> Optional[str]:
        """
        Helper method to find a Meshtastic Node ID based on user input.
        Searches by exact Node ID, Short Name (case-insensitive),
        Long Name (case-insensitive), or Node Number.

        Args:
            node_spec (str): The user-provided identifier (e.g., "MK1", "!abcdef12", "My Node", "12345678").

        Returns:
            str: The found Node ID (e.g., "!abcdef12") or None if not found.
        """
        target_node_id = None
        try:
            nodes = self.mesh_interface.nodes # Access the node list/dict
            # Try to parse as node number first
            try:
                node_num = int(node_spec)
                # Search by node number
                for node_id, node_info in nodes.items():
                    if node_info.get('num') == node_num:
                        return node_id
            except ValueError:
                # Not a number, continue with string matching
                pass
            
            # String-based matching
            for node_id, node_info in nodes.items():
                 # 1. Check for exact Node ID match
                 if node_id == node_spec:
                     return node_id
                 # 2. Check for Short Name match (case-insensitive)
                 user_info = node_info.get('user', {})
                 if user_info.get('shortName', '').upper() == node_spec.upper():
                     return node_id
                 # 3. Check for Long Name match (case-insensitive)
                 if user_info.get('longName', '').upper() == node_spec.upper():
                     return node_id
        except Exception as e:
            logging.error(f"Error accessing node list while finding '{node_spec}': {e}")
        return None # Return None if no match is found or an error occurs

    def handle_control_command(self, connection: Any, nick: str, command_word: str, args: List[str]) -> None:
        """Looks up and executes a command from the registry."""
        if not command_word:
            connection.notice(nick, "Error: Empty command received.")
            return
        
        command_info = self.commands.get(command_word)
        if command_info and 'execute' in command_info:
            logging.info(f"Executing command '{command_word}' for {nick} with args: {args}")
            try:
                # Call the 'execute' function associated with the command
                # Pass necessary context: server instance, connection, nick, and parsed args
                command_info['execute'](self, connection, nick, args)
            except Exception as e:
                # Catch errors during command execution
                logging.error(f"Error executing command '{command_word}' for {nick}: {e}", exc_info=True)
                # Notify the user about the error
                connection.notice(nick, f"Error executing command {command_word}: {e}")
        else:
            # This case should ideally not be reached due to the check in on_privmsg
            logging.warning(f"Command '{command_word}' received but not found in registry during execution phase.")
            connection.notice(nick, f"Unknown command: '{command_word}'. Try HELP.")

    # --- Other IRC Event Handlers (Optional) ---
    # Add handlers for on_part, on_quit, on_nick etc. if specific actions
    # are needed when users leave channels, quit, or change nicknames.
    # For this simple gateway, the base class handling might be sufficient.

    # def on_quit(self, connection, event):
    #     logging.info(f"Client quit: {connection.nickname} ({event.arguments[0]})")
    #     super().on_quit(connection, event) # Call base handler

    # def on_part(self, connection, event):
    #     channel = event.target
    #     logging.info(f"Client left channel {channel}: {connection.nickname}")
    #     super().on_part(connection, event) # Call base handler
