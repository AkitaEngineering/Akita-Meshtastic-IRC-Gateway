# Command Reference

Commands are case-insensitive and must be sent in the configured control channel. A node can be identified by exact node ID, node number, short name, or long name. Quote long names containing spaces.

| Command | Description |
| --- | --- |
| `HELP [command]` | List commands or show one command's usage. |
| `SEND <message>` | Broadcast text on the configured Meshtastic channel. |
| `DM <node> <message>` | Send a reliable direct message and report its ACK/NAK callback. |
| `ALARM <message>` | Send a high-priority Meshtastic `ALERT_APP` packet. |
| `PING <node>` | Request an echo using Meshtastic `REPLY_APP` and report response time. |
| `NODES` | List cached nodes by most recent activity. |
| `INFO <node>` | Show cached identity, signal, metrics, uptime, and position fields. |
| `LOCATION` | Show the gateway node's reported GPS fix and an OpenStreetMap link. |
| `STATS` | Show node count, gateway uptime, and IRC client counts. |
| `TIME` | Show timezone-aware server time. |
| `WEATHER` | Show current OpenWeatherMap conditions when API settings are present. |
| `HFCONDITIONS` | Show current NOAA SWPC Kp, 10.7 cm flux, NOAA scales, and forecast probabilities. |

Meshtastic text limits are enforced as 233 UTF-8 payload bytes. The process also applies a global mesh-send interval, so rapid consecutive send commands can return a retry delay.
