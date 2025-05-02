# Command Reference

This page lists the commands available within the control channel (default: `#meshtastic-ctrl`) when connected to the Akita Meshtastic IRC Gateway (AMIG).

Commands are generally case-insensitive. Arguments shown in `<angle brackets>` are placeholders for values you need to provide. Arguments shown in `[square brackets]` are optional. Node identifiers (`<node>`) can usually be the Node ID string (e.g., `!abcdef12`), the Short Name (e.g., `MK1`), the Long Name (e.g., `"My Node"` - use quotes if it contains spaces), or the Node Number (e.g., `12345678`).

---

## Core Commands

* **`HELP [command]`**
    * **Usage:** `HELP` or `HELP SEND`
    * **Description:** Displays a list of all available commands or detailed help for a specific `[command]`.

* **`SEND <message>`**
    * **Usage:** `SEND Your message text here`
    * **Description:** Sends the provided `<message>` to the default Meshtastic channel (configured via `--mesh-channel` or `DEFAULT_MESH_CHANNEL_INDEX` in `config.py`). The message is broadcast to all nodes listening on that channel.

* **`DM <node> <message>`**
    * **Usage:** `DM MK1 Your private message` or `DM !abcdef12 Your private message`
    * **Description:** Sends a Direct Message (private message) over the Meshtastic network to the specified `<node>`. An acknowledgement (ACK) is requested. You will receive feedback in the channel (`[ACK/NAK] ...`) if the target node confirms receipt or if the message times out/fails.

* **`NODES`**
    * **Usage:** `NODES`
    * **Description:** Lists all nodes currently known to the gateway's Meshtastic interface. The list includes Node Number, Node ID, Long Name, Short Name, Signal-to-Noise Ratio (SNR), and the time the node was last heard from. Nodes are sorted by the most recently heard.

* **`INFO <node>`**
    * **Usage:** `INFO MK1` or `INFO !abcdef12`
    * **Description:** Displays detailed information stored by the Meshtastic interface about the specified `<node>`. This may include user details, position data, device metrics, configuration settings, etc. The exact information depends on what the node has shared and what the interface has received/cached.

---

## Utility Commands

* **`TIME`**
    * **Usage:** `TIME`
    * **Description:** Shows the current date and time according to the server where the gateway script is running.

* **`STATS`**
    * **Usage:** `STATS`
    * **Description:** Displays basic statistics about the gateway and the mesh network as seen by the gateway (e.g., known node count, gateway uptime, connected IRC clients).

* **`LOCATION`**
    * **Usage:** `LOCATION`
    * **Description:** Attempts to display the GPS location (Latitude, Longitude, Altitude, Time) of the Meshtastic node acting as the gateway itself. Requires the gateway node to have a GPS fix and share its location.

* **`ALARM <message>`**
    * **Usage:** `ALARM Critical alert text`
    * **Description:** Sends the provided `<message>` to the default Meshtastic channel, prefixed with "ALARM:". This is intended for broadcasting urgent messages.

* **`PING <node>`**
    * **Usage:** `PING MK1` or `PING !abcdef12`
    * **Description:** Sends a low-level ping request directly to the specified Meshtastic `<node>`. If the node receives the ping and replies, a "PONG" message containing signal information (RSSI/SNR) should appear in the IRC channel. This is useful for checking direct radio connectivity.

---

## Informational Commands

* **`WEATHER`**
    * **Usage:** `WEATHER`
    * **Description:** Shows the current weather conditions for the location configured in `config.py` using the OpenWeatherMap API (requires configuration).

* **`HFCONDITIONS`**
    * **Usage:** `HFCONDITIONS`
    * **Description:** Shows current HF radio propagation indicators (Solar Flux Index, K-Index, forecasts) fetched from NOAA SWPC.

---

*This list is generated based on the command modules found in `src/gateway/commands/` at startup. New commands may be added over time.*
