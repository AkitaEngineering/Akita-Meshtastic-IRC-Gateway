# Akita Meshtastic IRC Gateway (AMIG)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

**Organization:** Akita Engineering  
**Website:** [www.akitaengineering.com](https://www.akitaengineering.com)  
**Contact:** info@akitaengineering.com  

A simple, modular Python-based gateway that bridges an IRC channel to the Meshtastic network, allowing users to send commands and messages to the mesh via an IRC client.

## Features

- Connect using a standard IRC client.
- Join a designated control channel (`#meshtastic-ctrl` by default).
- **Modular command system:** Easily add new commands by creating Python modules.
- Send messages to the Meshtastic default channel (`SEND <message>`).
- Send Direct Messages to specific Meshtastic nodes (`DM <node_id|shortname|nodenum> <message>`).
- List known nodes on the mesh (`NODES`).
- Get basic info about a specific node (`INFO <node>`).
- View gateway node's GPS location (`LOCATION`).
- Broadcast an ALARM message (`ALARM <message>`).
- Send a Meshtastic ping (`PING <node>`).
- Get server time (`TIME`).
- Get basic mesh stats (`STATS`).
- Get weather forecast via OpenWeatherMap (`WEATHER` - requires config).
- Get HF propagation conditions via NOAA SWPC (`HFCONDITIONS`).
- Relays standard chat messages between IRC users in the control channel.
- Relays received Meshtastic messages (broadcasts and DMs to the gateway node) back to the IRC channel.
- Relays ACK/NAK/PONG feedback to the IRC channel.

**Disclaimer:** This project provides a functional base but should be considered experimental. Real-world testing, robust error handling, and security hardening are ongoing considerations. Use with caution and ensure compliance with all applicable regulations.

## Documentation

**Full documentation is available:** Please refer to the `docs/` directory and use MkDocs (`pip install mkdocs mkdocs-material`, then `mkdocs serve`) to view the complete documentation site locally. A hosted version may be available at [Link to Hosted Docs - To be added].


## Setup

### Clone the Repository

```sh
git clone https://github.com/AkitaEngineering/Akita-Meshtastic-IRC-Gateway.git
cd Akita-Meshtastic-IRC-Gateway
```

### Create Virtual Environment (Recommended)

```sh
python -m venv venv
```

#### Activate the Environment

- **Linux/macOS**:
  ```sh
  source venv/bin/activate
  ```
- **Windows**:
  ```sh
  venv\Scripts\activate
  ```

### Install Dependencies

```sh
pip install -r requirements.txt
```

---

## Configuration

Edit `src/gateway/config.py`:

- Set one of the following based on your connection type:
  - `MESH_DEVICE_PORT` (e.g., `/dev/ttyUSB0`, `COM3`)
  - `MESH_DEVICE_HOST` (e.g., `192.168.1.100`)
  - Leave the unused one as `None`.

- Weather Command Support:
  - Add your OpenWeatherMap API key to `WEATHER_API_KEY` or set the `WEATHER_API_KEY` environment variable.
  - Ensure `WEATHER_LOCATION` is set correctly.

- Review and adjust other settings:
  - `IRC_SERVER_PORT`
  - `CONTROL_CHANNEL`
  - And any other options as needed.

---

## Running the Gateway

From the project root:

```sh
python src/gateway/main.py [options]
```

### Common Options (Override `config.py`)

```sh
--mesh-port /dev/ttyACM0  # Use a specific serial port.
--mesh-host <ip_address>  # Use a specific TCP/IP host.
-p <port_num>             # Run IRC server on a different port.
-v                        # Enable verbose (debug) logging.
```

See all options:
```sh
python src/gateway/main.py --help
```

---

## Connecting with an IRC Client

1. Connect your IRC client to the gateway host/IP and port (e.g., `localhost:6667`).
2. Disable SSL/TLS.
3. Join the control channel:
   ```
   /join #meshtastic-ctrl
   ```
   *(Or your configured channel.)*
4. Type `HELP` to list available commands.

---

## Adding New Commands

To extend functionality:

1. Create a new file in `src/gateway/commands/`, e.g. `cmd_yourcommand.py`
2. Define the following in the file:
   - `COMMAND_NAME`
   - `COMMAND_HELP`
   - `execute(server, connection, nick, args)`

The gateway auto-loads new command files on startup.

---

## Contributing

Contributions, issues, and feature requests are welcome.

To contribute:

- Fork the repository
- Create a branch
- Make your changes
- Submit a pull request

---

## License

Distributed under the GNU General Public License v3.0. See `LICENSE` for more information.

