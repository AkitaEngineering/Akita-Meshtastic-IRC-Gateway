# src/gateway/main.py

"""
Main entry point for the Akita Meshtastic IRC Gateway (AMIG).

Handles argument parsing (overriding config), initializes the Meshtastic interface
(real or mock), sets up logging, dynamically loads commands, creates the IRC
server instance, and starts the server loop.
"""

import sys
import logging
import argparse
import signal # For graceful shutdown handling
import os # For command discovery
import importlib # For dynamic command loading
import time # For potential delays

# --- Project Imports ---
try:
    # Import necessary classes and constants from server.py
    from gateway.server import (
        MeshtasticGatewayServer, MockMeshtasticInterface
    )
    # Import configuration settings
    import gateway.config as config
    # Import the commands package to find its path
    import gateway.commands
except ImportError as e:
    # Provide helpful error message if imports fail
    print(f"Import Error: {e}", file=sys.stderr)
    print("Ensure you are running this script from the project root directory", file=sys.stderr)
    print("e.g., using 'python src/gateway/main.py'", file=sys.stderr)
    print("Or ensure the 'src' directory is in your PYTHONPATH.", file=sys.stderr)
    sys.exit(1)


# --- Meshtastic Library Imports (Conditional) ---
# Try to import the real Meshtastic library; fall back gracefully if not installed.
try:
    import meshtastic
    import meshtastic.serial_interface
    import meshtastic.tcp_interface
    from meshtastic.util import Timeout as MeshtasticTimeout # Import Timeout exception
    # Disable slow protobuf warning which is common but usually harmless
    os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'
    from pubsub import pub # Required by meshtastic for event handling
    MESHTASTIC_AVAILABLE = True
except ImportError:
    # Log a warning if the library isn't found
    logging.warning("meshtastic library not found. Real interface disabled. Will use Mock.")
    MESHTASTIC_AVAILABLE = False
    # Define dummy classes/objects to prevent NameErrors later if the library is missing
    class MeshtasticObject: pass
    class MeshtasticTimeout(Exception): pass # Define dummy Timeout exception
    class MeshtasticError(Exception): pass # Define dummy MeshtasticError
    meshtastic = MeshtasticObject()
    meshtastic.serial_interface = MeshtasticObject()
    meshtastic.tcp_interface = MeshtasticObject()
    pub = None # pubsub won't be available either


# --- Global Variables ---
# These hold instances needed across functions, particularly for shutdown
mesh_interface = None
irc_server = None

# --- Functions ---

def setup_logging(log_level):
    """Configures application-wide logging based on config and args."""
    logging.basicConfig(level=log_level,
                        format=config.LOG_FORMAT,
                        datefmt=config.LOG_DATE_FORMAT)
    # Reduce verbosity of noisy libraries if desired (especially in INFO mode)
    if log_level > logging.DEBUG:
        logging.getLogger("irc").setLevel(logging.WARNING)
        logging.getLogger("pubsub").setLevel(logging.INFO)
        logging.getLogger("meshtastic").setLevel(logging.INFO) # Meshtastic lib can be verbose


def initialize_meshtastic_interface(mesh_port_arg, mesh_host_arg):
    """
    Initializes the real Meshtastic interface based on config and args,
    or falls back to the mock interface. Prioritizes command-line args.

    Args:
        mesh_port_arg (str | None): Value from --mesh-port argument.
        mesh_host_arg (str | None): Value from --mesh-host argument.

    Returns:
        An initialized Meshtastic interface instance (real or mock), or None on critical failure.
    """
    global mesh_interface # Allow modification of the global variable

    # Determine connection method: prioritize command line args, then config file
    mesh_port = mesh_port_arg if mesh_port_arg else config.MESH_DEVICE_PORT
    mesh_host = mesh_host_arg if mesh_host_arg else config.MESH_DEVICE_HOST

    # If the real library isn't installed, force mock
    if not MESHTASTIC_AVAILABLE:
        logging.warning("Meshtastic library not found, using Mock Interface.")
        mesh_interface = MockMeshtasticInterface()
        return mesh_interface

    # --- Attempt Real Connection ---
    connected = False
    if mesh_port:
        logging.info(f"Attempting to connect to Meshtastic via Serial: {mesh_port}")
        try:
            # Attempt connection, disable node scan initially for faster startup
            # Increase startup timeout if needed
            mesh_interface = meshtastic.serial_interface.SerialInterface(mesh_port, noNodes=True, startTimeout=60)
            # Wait briefly for the interface to establish connection and potentially get initial data
            logging.debug("Waiting briefly for serial interface initialization...")
            time.sleep(3) # Adjust if needed
            if mesh_interface and mesh_interface.myNodeInfo:
                 logging.info(f"Successfully connected via Serial to {mesh_port}. My Node: {mesh_interface.myNodeInfo.get('user',{}).get('id','?')}")
                 connected = True
            else:
                 logging.warning(f"Connected via Serial to {mesh_port}, but may not have received initial node info yet. Proceeding cautiously.")
                 # Assume connection is okay for now, rely on pubsub for confirmation
                 connected = True # Tentatively set true

        except MeshtasticError as me:
             logging.error(f"Meshtastic error connecting via Serial {mesh_port}: {me}", exc_info=False) # Less verbose traceback
        except Exception as e:
            logging.error(f"Generic error connecting via Serial {mesh_port}: {e}", exc_info=True)

    elif mesh_host:
        logging.info(f"Attempting to connect to Meshtastic via TCP: {mesh_host}")
        try:
            mesh_interface = meshtastic.tcp_interface.TCPInterface(mesh_host, noNodes=True)
            logging.debug("Waiting briefly for TCP interface initialization...")
            time.sleep(3) # Allow time for TCP connection and initial sync
            if mesh_interface and mesh_interface.myNodeInfo:
                logging.info(f"Successfully connected via TCP to {mesh_host}. My Node: {mesh_interface.myNodeInfo.get('user',{}).get('id','?')}")
                connected = True
            else:
                logging.warning(f"Connected via TCP to {mesh_host}, but may not have received initial node info yet. Proceeding cautiously.")
                connected = True # Tentatively set true

        except MeshtasticError as me:
             logging.error(f"Meshtastic error connecting via TCP {mesh_host}: {me}", exc_info=False)
        except Exception as e:
            logging.error(f"Generic error connecting via TCP {mesh_host}: {e}", exc_info=True)

    # --- Fallback to Mock ---
    if not connected:
        logging.warning("Failed to establish real Meshtastic connection. Falling back to Mock Interface.")
        if mesh_interface: # Close partially opened real interface if it exists
             try:
                 mesh_interface.close()
             except: pass # Ignore errors during close on fallback
        mesh_interface = MockMeshtasticInterface()

    return mesh_interface


def setup_pubsub_listeners(server_instance):
    """
    Sets up PyPubSub listeners for Meshtastic events if using the real interface.
    Connects Meshtastic events (like receiving messages) to methods on the
    IRC server instance.

    Args:
        server_instance: The instantiated MeshtasticGatewayServer object.
    """
    # Only set up listeners if pubsub is available and we are using the real interface
    if pub and not isinstance(mesh_interface, MockMeshtasticInterface):
        logging.info("Setting up Meshtastic pubsub listeners...")
        try:
            # Generic receive handler (catches text, position, ping, admin etc.)
            pub.subscribe(server_instance.on_meshtastic_receive, "meshtastic.receive")

            # Connection status handlers
            pub.subscribe(on_mesh_connection_handler, "meshtastic.connection.status")
            pub.subscribe(on_mesh_connection_handler, "meshtastic.connection.established")
            pub.subscribe(on_mesh_connection_handler, "meshtastic.connection.lost")
            # Node list update handler
            pub.subscribe(on_node_update_handler, "meshtastic.node.updated")

            logging.info("Pubsub listeners configured successfully.")
        except Exception as e:
            # Log errors during pubsub setup
            logging.error(f"Failed to subscribe to pubsub topics: {e}", exc_info=True)
    elif isinstance(mesh_interface, MockMeshtasticInterface):
         # Mock interface uses its own direct callback mechanism
         logging.info("Mock interface used, pubsub listeners not needed.")
    else:
         # Log if pubsub isn't available (shouldn't happen if meshtastic is installed)
         logging.warning("Pubsub library not available, cannot set up Meshtastic listeners.")

# --- PubSub Event Handlers (for real interface) ---

def on_mesh_connection_handler(status=None, interface=None, **kwargs):
    """Handles Meshtastic connection status updates reported via pubsub."""
    # Extract status message robustly
    status_message = "Unknown connection status change"
    if status:
        status_message = str(status)
    elif 'message' in kwargs:
        status_message = str(kwargs['message'])
    elif 'reason' in kwargs: # Sometimes connection lost provides a reason
        status_message = f"Connection lost: {kwargs['reason']}"

    logging.info(f"Meshtastic Connection Status: {status_message}")
    # Notify IRC users about connection changes if the server is running
    if irc_server and hasattr(irc_server, '_send_server_message_to_control_channel'):
         irc_server._send_server_message_to_control_channel(f"Mesh Status: {status_message}", "[MESH]")

def on_node_update_handler(node=None, interface=None):
    """Handles node list updates reported via pubsub."""
    if node:
        try:
            # Extract node info safely using .get() with defaults
            node_id_num = node.get('num', 0) # Node number is often the primary key
            if node_id_num == 0: return # Skip updates for invalid node number 0
            user_info = node.get('user', {})
            node_name = user_info.get('shortName') or user_info.get('longName') or f"Node-{node_id_num}"
            last_heard_ts = node.get('lastHeard')
            last_heard_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_heard_ts)) if last_heard_ts else 'Never'

            logging.info(f"Node updated via pubsub: {node_name} ({node_id_num}), LastHeard: {last_heard_str}")

            # Optionally announce node updates (can be noisy)
            # if irc_server and hasattr(irc_server, '_send_server_message_to_control_channel'):
            #    irc_server._send_server_message_to_control_channel(f"Node Update: {node_name} seen/updated.", "[MESH]")
        except Exception as e:
            logging.error(f"Error processing node update: {e} - Node data: {node}", exc_info=True)
    else:
        logging.warning("Received node update event with no node data.")


def load_and_register_commands(server_instance):
    """
    Dynamically discovers and loads command modules from the 'commands' directory
    and registers them with the provided IRC server instance.
    """
    commands_package = gateway.commands # Get the imported package object
    # Determine the directory path of the commands package
    commands_path = os.path.dirname(commands_package.__file__)
    logging.info(f"Loading commands from directory: {commands_path}")

    # Iterate through files in the commands directory
    for filename in os.listdir(commands_path):
        # Look for Python files starting with 'cmd_'
        if filename.startswith("cmd_") and filename.endswith(".py"):
            module_name = filename[:-3] # Remove the '.py' extension
            try:
                # Construct the full, absolute module path (e.g., 'gateway.commands.cmd_send')
                full_module_path = f"gateway.commands.{module_name}"
                # Dynamically import the module
                command_module = importlib.import_module(full_module_path)
                logging.debug(f"Successfully loaded module: {full_module_path}")

                # Check if the module has the required attributes for a valid command
                if hasattr(command_module, 'COMMAND_NAME') and \
                   hasattr(command_module, 'execute') and \
                   callable(command_module.execute) and \
                   hasattr(command_module, 'COMMAND_HELP'):

                    # Extract command details from the module
                    cmd_name = command_module.COMMAND_NAME
                    cmd_func = command_module.execute
                    cmd_help = command_module.COMMAND_HELP

                    # Register the command with the IRC server instance
                    server_instance.register_command(cmd_name, cmd_func, cmd_help)
                else:
                    # Log a warning if a potential command module is missing required parts
                    logging.warning(f"Module {module_name} skipped: Missing required attributes (COMMAND_NAME, execute, COMMAND_HELP).")

            except ImportError as e:
                # Log errors specifically related to importing the module
                logging.error(f"Failed to import command module {module_name}: {e}", exc_info=True)
            except Exception as e:
                # Log any other errors during loading or registration
                logging.error(f"Error loading or registering command from {module_name}: {e}", exc_info=True)


def shutdown_handler(signum, frame):
    """Graceful shutdown handler for SIGINT (Ctrl+C) and SIGTERM."""
    logging.warning(f"Received signal {signum}. Initiating graceful shutdown...")

    # 1. Disconnect IRC clients
    if irc_server:
        logging.info("Disconnecting IRC clients...")
        try:
            # Use the server's method to disconnect all clients with a message
            irc_server.disconnect_all("Server shutting down")
        except Exception as e:
            logging.error(f"Error disconnecting IRC clients: {e}")

    # 2. Close Meshtastic interface (if real and has close method)
    if mesh_interface and not isinstance(mesh_interface, MockMeshtasticInterface):
        if hasattr(mesh_interface, 'close') and callable(mesh_interface.close):
             logging.info("Closing Meshtastic interface...")
             try:
                 mesh_interface.close()
             except Exception as e:
                 logging.error(f"Error closing Meshtastic interface: {e}")

    # 3. Exit the application
    logging.info("Shutdown complete.")
    sys.exit(0)

# --- Main Execution ---
def main():
    """
    Main function: Parses arguments, sets up logging, initializes interfaces,
    loads commands, starts the server, and handles shutdown.
    """
    global irc_server # Allow modification by signal handler

    # --- Argument Parsing (Define args, defaults come from config) ---
    parser = argparse.ArgumentParser(
        description="Akita Meshtastic IRC Gateway (AMIG)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Show defaults in help
    )
    # Use config values as defaults, but allow command-line override
    parser.add_argument("-H", "--host", default=config.IRC_SERVER_HOST,
                        help=f"Host address for IRC server to bind to")
    parser.add_argument("-p", "--port", type=int, default=config.IRC_SERVER_PORT,
                        help=f"Port for IRC server to listen on")
    parser.add_argument("-n", "--servername", default=config.IRC_SERVER_NAME,
                        help=f"Name reported by the IRC server")
    parser.add_argument("--mesh-port", default=None, # Default to None, rely on config if not given
                        help=f"Serial port for Meshtastic device (overrides config: {config.MESH_DEVICE_PORT})")
    parser.add_argument("--mesh-host", default=None, # Default to None, rely on config if not given
                        help=f"Hostname or IP for Meshtastic TCP/IP (overrides config: {config.MESH_DEVICE_HOST})")
    parser.add_argument("--mesh-channel", type=int, default=config.DEFAULT_MESH_CHANNEL_INDEX,
                        help=f"Default Meshtastic channel index used by SEND/ALARM")
    parser.add_argument("--control-channel", default=config.CONTROL_CHANNEL,
                        help=f"Name of the IRC control channel")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable detailed DEBUG level logging (overrides config)")

    args = parser.parse_args()

    # --- Setup Logging ---
    log_level = logging.DEBUG if args.verbose else config.LOG_LEVEL
    setup_logging(log_level)
    logging.debug(f"Command line arguments parsed: {args}")


    # --- Initialization ---
    mesh_if = initialize_meshtastic_interface(args.mesh_port, args.mesh_host)
    if mesh_if is None: # Check if initialization failed critically
        logging.critical("Could not initialize any Meshtastic interface. Exiting.")
        sys.exit(1)

    # Log effective settings
    logging.info(f"Starting Akita Meshtastic IRC Gateway (AMIG) '{args.servername}' on {args.host}:{args.port}")
    logging.info(f"Using Meshtastic Interface: {'Mock' if isinstance(mesh_if, MockMeshtasticInterface) else 'Real'}")
    logging.info(f"IRC Control Channel: {args.control_channel}")
    logging.info(f"Default Mesh Channel Index: {args.mesh_channel}")

    # --- Server Setup and Start ---
    try:
        # Instantiate the IRC server, passing the mesh interface and relevant config args
        irc_server = MeshtasticGatewayServer(
            mesh_interface_ref=mesh_if,
            control_channel_name=args.control_channel,
            default_mesh_channel_index=args.mesh_channel,
            bind_address=(args.host, args.port),
            servername=args.servername
        )

        # Load and register command modules found in the 'commands' directory
        load_and_register_commands(irc_server)

        # Setup pubsub listeners *after* server instance is created (for real interface)
        setup_pubsub_listeners(irc_server)

        # Setup signal handlers for graceful shutdown (Ctrl+C, kill)
        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        # Start the server's main processing loop (blocks until shutdown)
        logging.info("Server starting. Press Ctrl+C to shut down gracefully.")
        irc_server.serve_forever() # This blocks until interrupted

    except OSError as e:
        # Handle specific error if server can't bind to the address/port
        logging.error(f"Failed to bind IRC server to {args.host}:{args.port} - {e}")
        logging.error("Is the port already in use or do you have permissions?")
        sys.exit(1)
    except KeyboardInterrupt:
        # This might be caught if serve_forever doesn't handle SIGINT perfectly
        logging.info("KeyboardInterrupt caught in main loop (should be handled by signal handler).")
        # Ensure shutdown handler is called if loop exits this way
        shutdown_handler(signal.SIGINT, None)
    except Exception as e:
        # Catch any other unexpected exceptions during server setup or runtime
        logging.exception(f"An unexpected critical error occurred in the main loop: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # --- Pre-run Checks/Setup ---
    # Ensure the commands directory and its __init__.py exist for dynamic loading
    commands_dir = os.path.join(os.path.dirname(__file__), "commands")
    os.makedirs(commands_dir, exist_ok=True) # Create dir if it doesn't exist
    init_path = os.path.join(commands_dir, "__init__.py")
    if not os.path.exists(init_path):
        try:
            # Create an empty __init__.py file to mark 'commands' as a package
            with open(init_path, 'w') as f:
                pass
            logging.debug(f"Created empty {init_path}")
        except OSError as e:
            logging.warning(f"Could not create {init_path}: {e}")

    # --- Execute Main Function ---
    main()
