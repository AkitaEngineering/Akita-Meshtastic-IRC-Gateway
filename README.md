# Akita Meshtastic IRC Gateway (AMIG)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

**Organization:** Akita Engineering
**Website:** [www.akitaengineering.com](https://www.akitaengineering.com)
**Contact:** info@akitaengineering.com

A simple, modular Python-based gateway that bridges an IRC channel to the Meshtastic network, allowing users to send commands and messages to the mesh via an IRC client.

## Features

* Connect using a standard IRC client.
* Join a designated control channel (`#meshtastic-ctrl` by default).
* **Modular command system:** Easily add new commands by creating Python modules.
* Send messages to the Meshtastic default channel (`SEND <message>`).
* Send Direct Messages to specific Meshtastic nodes (`DM <node_id|shortname> <message>`).
* List known nodes on the mesh (`NODES`).
* Get basic info about a specific node (`INFO <node>`).
* View gateway node's GPS location (`LOCATION`).
* Broadcast an ALARM message (`ALARM <message>`).
* Send a Meshtastic ping (`PING <node>`).
* Get server time (`TIME`).
* Get basic mesh stats (`STATS`).
* (Mock Data) Get weather and HF propagation info (`WEATHER`, `HFCONDITIONS`).
* Relays standard chat messages between IRC users in the control channel.
* Relays received Meshtastic messages (broadcasts and DMs to the gateway node) back to the IRC channel.

**Disclaimer:** This is currently a prototype project. It uses a mock Meshtastic interface by default and has hardcoded data for external lookups (Weather, HF). It lacks robust error handling and security features. Use with caution and primarily for experimentation.

## Documentation

**Full documentation is available online (or build locally):** [Link to Hosted Docs] or run `mkdocs serve` in the project root.

*(See the `docs/` directory and `mkdocs.yml` for details on building the documentation.)*

## Project Structure
```
meshtastic-irc-gateway/
├── .gitignore
├── LICENSE           # Project license file (GPLv3)
├── README.md         # This file
├── requirements.txt  # Python dependencies
├── mkdocs.yml        # Documentation configuration
├── docs/             # Documentation source files (Markdown)
│   ├── index.md
│   ├── commands.md
│   ├── license.md
│   └── ...
└── src/              # Application source code
└── gateway/
├── init.py
├── server.py   # Core IRC server class & Mock Interface
├── main.py     # Entry point, arg parsing, command loading
└── commands/   # Directory for command modules
├── init.py
├── cmd_send.py
└── ...       # Other command files (cmd_*.py)
```
## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd meshtastic-irc-gateway
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Meshtastic Connection (Optional):**
    * If using a real Meshtastic device, specify its connection details via command-line arguments when running (see below). Otherwise, the mock interface will be used.

## Running the Gateway

Run the main script from the project root directory:

```bash
python src/gateway/main.py [options]
```

## Common Options

- `--mesh-port /dev/ttyUSB0`: Use a specific serial port.  
- `--mesh-host 192.168.1.100`: Use a specific TCP/IP host.  
- `-p 6668`: Run the IRC server on a different port.  
- `-v`: Enable verbose (debug) logging.

> See `python src/gateway/main.py --help` or the full documentation for all options.

---

## Connecting with an IRC Client

Connect your IRC client to the address and port where the gateway is running (e.g., `localhost:6667`).

- Join the control channel: `/join #meshtastic-ctrl`
- Type `HELP` for a list of commands.

> See the full documentation under **User Guide → Connecting** for more details.

---

## Adding New Commands

1. Create a new `cmd_*.py` file in `src/gateway/commands/`.
2. Define `COMMAND_NAME`, `COMMAND_HELP`, and an `execute(server, connection, nick, args)` function within the file.

The gateway will automatically load the new command on startup.

> See the full documentation under **Development → Adding Commands** (you'll need to create this page) for details.

---

## Contributing

Contributions, issues, and feature requests are welcome!

