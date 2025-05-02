# Running the Gateway

Once installed and configured, you can run the gateway from your terminal. Ensure your virtual environment is activated if you created one (`source venv/bin/activate` or `venv\Scripts\activate`).

## Starting the Server

The main script is located at `src/gateway/main.py`. Run it from the **project root directory** (the one containing `src`, `docs`, `README.md`, etc.):

```bash
python src/gateway/main.py [options]
```

The gateway will start using the settings from `src/gateway/config.py`, unless overridden by command-line options. It will attempt to connect to your configured Meshtastic device (or use the Mock Interface if no device is configured). The IRC server component will start listening for client connections.

You will see log messages in the terminal indicating the startup process, connection status, and any errors.

## Command-Line Options (Overrides)

You can override settings from `config.py` using command-line arguments:

| Option                 | Config Setting          | Description                                                    |
| :--------------------- | :---------------------- | :------------------------------------------------------------- |
| `-H HOST`, `--host`    | `IRC_SERVER_HOST`       | Host address for the IRC server to bind to.                    |
| `-p PORT`, `--port`    | `IRC_SERVER_PORT`       | Port for the IRC server to listen on.                          |
| `-n NAME`, `--servername` | `IRC_SERVER_NAME`       | Name reported by the IRC server.                               |
| `--mesh-port PORT`     | `MESH_DEVICE_PORT`      | Serial port for Meshtastic device connection.                  |
| `--mesh-host HOST`     | `MESH_DEVICE_HOST`      | Hostname/IP for Meshtastic TCP/IP connection.                  |
| `--mesh-channel INDEX` | `DEFAULT_MESH_CHANNEL_INDEX` | Default Meshtastic channel index used by `SEND` and `ALARM`. |
| `--control-channel NAME`| `CONTROL_CHANNEL`       | Name of the IRC control channel.                               |
| `-v`, `--verbose`      | `LOG_LEVEL` (sets DEBUG)| Enable detailed DEBUG level logging.                           |

**Example Overrides:**

```bash
# Run using a specific serial port, overriding any config setting
python src/gateway/main.py --mesh-port /dev/ttyACM0

# Run using a specific TCP host and different IRC port
python src/gateway/main.py --mesh-host 192.168.4.1 -p 6668

# Run with verbose logging
python src/gateway/main.py -v
```

## Running in the Background (Daemonizing)

The script runs in the foreground by default. To run it persistently as a background service (daemon), especially on Linux systems, consider using tools like:

* **`systemd`:** Create a service unit file (e.g., `/etc/systemd/system/amig.service`) to manage the process, handle logging, and enable auto-start on boot. (Recommended for production).
* **`supervisor`:** Another process control system useful for managing Python applications.
* **`screen` / `tmux`:** Terminal multiplexers allow you to run the script in a session and detach, leaving it running. Simpler for temporary backgrounding.
    ```bash
    # Example with screen
    screen -S amig python src/gateway/main.py --mesh-port /dev/ttyUSB0
    # Press Ctrl+A, then D to detach. Use 'screen -r amig' to reattach.
    ```

## Stopping the Gateway

If running in the foreground, press `Ctrl+C` in the terminal. The gateway should shut down gracefully, closing connections.

If running under `systemd` or `supervisor`, use their respective commands (e.g., `sudo systemctl stop amig`, `supervisorctl stop amig`).

If running in `screen`/`tmux`, reattach (`screen -r amig`), then press `Ctrl+C`.

## Next Steps

Learn how to **[Connect using an IRC Client](connecting.md)**.
