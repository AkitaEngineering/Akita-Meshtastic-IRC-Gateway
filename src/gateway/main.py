# src/gateway/main.py

"""
Main entry point for the Akita Meshtastic IRC Gateway (AMIG).

Handles argument parsing, initializes the Meshtastic interface (real or mock),
sets up logging, dynamically loads commands, creates the IRC server instance,
and starts the server loop.
"""

import sys
import logging
import argparse
import signal # For graceful shutdown handling
import os # For command discovery
import importlib # For dynamic command loading

# --- Project Imports ---
# This structure assumes the script is run from the project root directory
# (e.g., using `python src/gateway/main.py`)
try:
    # Import necessary classes and constants from server.py
    from gateway.server import (
        MeshtasticGatewayServer, MockMeshtasticInterface,
        IRC_SERVER_HOST, IRC_SERVER_PORT, IRC_SERVER_NAME,
        CONTROL_CHANNEL, DEFAULT_MESH_CHANNEL_INDEX
    )
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
    from pubsub import pub # Required by meshtastic for event handling
    MESHTASTIC_AVAILABLE = True
except ImportError:
    # Log a warning if the library isn't found
    logging.warning("meshtastic library not found. Real interface disabled. Will use Mock.")
    MESHTASTIC_AVAILABLE = False
    # Define dummy classes/objects to prevent NameErrors later if the library is missing
    class MeshtasticObject: pass
    meshtastic = MeshtasticObject()
    meshtastic.serial_interface = MeshtasticObject()
    meshtastic.tcp_interface = MeshtasticObject()
    pub = None # pubsub won't be available either


# --- Global Variables ---
# These hold instances needed across functions, particularly for shutdown
mesh_interface = None
irc_server = None

# --- Functions ---

def setup_logging():
    """Configures application-wide logging."""
    # Set default level to INFO; can be overridden by -v argument
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    # Reduce verbosity of noisy libraries if desired
    logging.getLogger("irc").setLevel(logging.WARNING)
    logging.getLogger("pubsub").setLevel(logging.INFO) # Pubsub can be a bit chatty


def initialize_meshtastic_interface(args):
    """
    Initializes the real Meshtastic interface based on command-line arguments,
    or falls back to the mock interface if no real connection is specified
    or if the real connection fails.

    Args:
        args: The parsed command-line arguments object.

    Returns:
        An initialized Meshtastic interface instance (real or mock), or None on critical failure.
    """
    global mesh_interface # Allow modification of the global variable

    # If the real library isn't installed, force use of the mock interface
    if not MESHTASTIC_AVAILABLE:
        logging.warning("Meshtastic library not found, using Mock Interface.")
        mesh_interface = MockMeshtasticInterface()
        return mesh_interface

    # Attempt to connect via Serial if --mesh-port is provided
    if args.mesh_port:
        logging.info(f"Attempting to connect to Meshtastic via Serial: {args.mesh_port}")
        try:
            mesh_interface = meshtastic.serial_interface.SerialInterface(args.mesh_port)
            logging.info(f"Successfully connected via Serial to {args.mesh_port}")
            # Optional: Short delay to allow the interface to fully initialize and
            # potentially receive initial node database information. Adjust as needed.
            # import time
            # time.sleep(3)
        except Exception as e:
            # Log specific error during serial connection
            logging.error(f"Failed to connect to Meshtastic serial device {args.mesh_port}: {e}", exc_info=True)
            logging.warning("Falling back to Mock Interface due to serial connection error.")
            mesh_interface = MockMeshtasticInterface()

    # Attempt to connect via TCP if --mesh-host is provided
    elif args.mesh_host:
        logging.info(f"Attempting to connect to Meshtastic via TCP: {args.mesh_host}")
        try:
            mesh_interface = meshtastic.tcp_interface.TCPInterface(args.mesh_host)
            logging.info(f"Successfully connected via TCP to {args.mesh_host}")
            # import time
            # time.sleep(3)
        except Exception as e:
            # Log specific error during TCP connection
            logging.error(f"Failed to connect to Meshtastic TCP host {args.mesh_host}: {e}", exc_info=True)
            logging.warning("Falling back to Mock Interface due to TCP connection error.")
            mesh_interface = MockMeshtasticInterface()

    # If neither --mesh-port nor --mesh-host is provided, use the mock interface
    else:
        logging.warning("No Meshtastic device specified (--mesh-port or --mesh-host), using Mock Interface.")
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
            # Subscribe the server's on_meshtastic_receive method to handle various receive events
            # Listen for generic receive first (covers many types)
            pub.subscribe(server_instance.on_meshtastic_receive, "meshtastic.receive")
            # Optionally, subscribe to more specific events if needed later
            # pub.subscribe(server_instance.on_meshtastic_receive, "meshtastic.receive.text") # Only text
            # pub.subscribe(server_instance.on_meshtastic_receive, "meshtastic.receive.position") # Only position
            # pub.subscribe(on_node_update_handler, "meshtastic.node.updated") # Requires separate handler

            # Listen for connection status changes
            pub.subscribe(on_mesh_connection_handler, "meshtastic.connection.status")
            pub.subscribe(on_mesh_connection_handler, "meshtastic.connection.established")
            pub.subscribe(on_mesh_connection_handler, "meshtastic.connection.lost")

            logging.info("Pubsub listeners configured successfully.")
        except Exception as e:
            # Log errors during pubsub setup
            logging.error(f"Failed to subscribe to pubsub topics: {e}", exc_info=True)
    elif isinstance(mesh_interface, MockMeshtasticInterface):
         # Mock interface uses its own direct callback mechanism
         logging.info("Mock interface used, pubsub listeners not needed (mock uses direct callback).")
    else:
         # Log if pubsub isn't available (shouldn't happen if meshtastic is installed)
         logging.warning("Pubsub library not available, cannot set up Meshtastic listeners.")

# --- PubSub Event Handlers (for real interface) ---

def on_mesh_connection_handler(status=None, interface=None, **kwargs):
    """Handles Meshtastic connection status updates reported via pubsub."""
    status_message = status if status else kwargs.get('message', 'Connection status changed')
    logging.info(f"Meshtastic Connection Status: {status_message}")
    # Optionally notify IRC users about connection changes
    if irc_server:
        # Check if the server has the method before calling (defensive programming)
        if hasattr(irc_server, '_send_server_message_to_control_channel'):
             irc_server._send_server_message_to_control_channel(f"Mesh Status: {status_message}", "[MESH]")

# Optional: Handler specifically for node updates if more complex logic is needed
# def on_node_update_handler(node, interface):
#    """Handles node list updates reported via pubsub."""
#    node_id = node.get('num', 'Unknown ID')
#    node_name = node.get('user', {}).get('shortName', node_id)
#    logging.info(f"Node updated via pubsub: {node_name} ({node_id})")
#    # Relay relevant node updates to the IRC channel?
#    if irc_server and hasattr(irc_server, '_send_server_message_to_control_channel'):
#        irc_server._send_server_message_to_control_channel(f"Node Update: {node_name} seen.", "[MESH]")


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
                    logging.warning(f"Module {module_name} does not conform to command structure "
                                    "(missing COMMAND_NAME, execute function, or COMMAND_HELP). Skipping.")

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

    # 2. Close Meshtastic interface (if it's the real one and has a close method)
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

    # Initial setup
    setup_logging()

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="Akita Meshtastic IRC Gateway (AMIG)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Show defaults in help
    )
    # IRC Server Options
    parser.add_argument("-H", "--host", default=IRC_SERVER_HOST, help="Host address for IRC server to bind to")
    parser.add_argument("-p", "--port", type=int, default=IRC_SERVER_PORT, help="Port for IRC server to listen on")
    parser.add_argument("-n", "--servername", default=IRC_SERVER_NAME, help="Name reported by the IRC server")
    # Meshtastic Connection Options
    parser.add_argument("--mesh-port", help="Serial port for Meshtastic device (e.g., /dev/ttyUSB0, COM3)")
    parser.add_argument("--mesh-host", help="Hostname or IP address for Meshtastic TCP/IP interface")
    # Gateway Behavior Options
    parser.add_argument("--mesh-channel", type=int, default=DEFAULT_MESH_CHANNEL_INDEX, help="Default Meshtastic channel index used by SEND/ALARM")
    parser.add_argument("--control-channel", default=CONTROL_CHANNEL, help="Name of the IRC control channel")
    # Logging Options
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable detailed DEBUG level logging")

    args = parser.parse_args()

    # Adjust log level if verbose flag is set
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        # Optionally make specific libraries less verbose even in debug mode
        # logging.getLogger("irc").setLevel(logging.INFO)
        logging.debug("Debug logging enabled.")

    # --- Initialization ---
    # Initialize Meshtastic Interface (Real or Mock)
    mesh_if = initialize_meshtastic_interface(args)
    if mesh_if is None: # Check if initialization failed critically
        logging.critical("Could not initialize any Meshtastic interface. Exiting.")
        sys.exit(1)

    # Log startup information
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
        irc_server.serve_forever()

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
