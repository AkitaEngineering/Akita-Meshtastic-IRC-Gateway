# Akita Meshtastic IRC Gateway (AMIG)

AMIG exposes one authenticated IRC control channel for a Meshtastic radio. It relays mesh broadcasts and direct messages to joined IRC users and provides commands for sending text, alerts, direct messages, echo requests, node information, weather, and NOAA space-weather conditions.

## Production safeguards

- Real radio mode is fail-closed: connection failures stop startup instead of silently switching to test data.
- Mock mode must be explicitly selected with `--mock`.
- The default listener is loopback-only.
- A non-loopback listener requires TLS and `AMIG_IRC_PASSWORD` unless the operator deliberately supplies `--allow-insecure-irc`.
- IRC input is bounded and sanitized, clients only receive mesh traffic after joining the control channel, and mesh transmissions are rate-limited.
- Dependencies have tested lower bounds and bounded major versions.
- Startup fails if a command module or configuration value is invalid.

TLS protects the IRC password and mesh content in transit. Do not expose plain IRC directly to the internet. Radio operation remains subject to local regulations and the security of the configured Meshtastic channels.

## Install

AMIG requires Python 3.10 or newer.

```bash
git clone https://github.com/AkitaEngineering/Akita-Meshtastic-IRC-Gateway.git
cd Akita-Meshtastic-IRC-Gateway
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

For development and tests:

```bash
python -m pip install '.[dev]'
pytest
ruff check src tests
ruff format --check src tests
```

## Configure a radio

Choose exactly one connection:

```bash
export AMIG_MESH_DEVICE_PORT=/dev/ttyACM0
# or:
export AMIG_MESH_DEVICE_HOST=192.168.1.100
```

Important environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `AMIG_IRC_HOST` | `127.0.0.1` | IRC bind address |
| `AMIG_IRC_PORT` | `6667` | IRC listen port |
| `AMIG_IRC_SERVER_NAME` | `amig.gw` | IRC server name |
| `AMIG_CONTROL_CHANNEL` | `#meshtastic-ctrl` | Sole control channel |
| `AMIG_IRC_PASSWORD` | unset | IRC server password |
| `AMIG_TLS_CERTFILE` / `AMIG_TLS_KEYFILE` | unset | PEM certificate chain and private key |
| `AMIG_IRC_MAX_CLIENTS` | `100` | Maximum simultaneous client sockets |
| `AMIG_IRC_REGISTRATION_TIMEOUT` | `30` | Seconds allowed to complete PASS/NICK/USER |
| `AMIG_MESH_CHANNEL` | `0` | Meshtastic channel index, 0–7 |
| `AMIG_MESH_CONNECT_TIMEOUT` | `60` | Radio connection timeout in seconds |
| `AMIG_MESH_CONNECT_RETRIES` | `3` | Startup connection attempts |
| `AMIG_MESH_SEND_INTERVAL` | `1.0` | Minimum seconds between mesh transmissions |
| `AMIG_MESH_RESPONSE_TIMEOUT` | `30` | Seconds before a pending DM or ping reports timeout |
| `AMIG_LOG_LEVEL` | `INFO` | Python logging level |
| `WEATHER_API_KEY` | unset | OpenWeatherMap API key |
| `WEATHER_LOCATION` | `Port Colborne,CA` | OpenWeatherMap query |
| `WEATHER_UNITS` | `metric` | `metric`, `imperial`, or `standard` |

## Run

After installing the package:

```bash
amig
```

For a local smoke test without a radio:

```bash
amig --mock
```

To listen beyond localhost, configure a certificate and password before changing the bind address:

```bash
export AMIG_IRC_PASSWORD='use-a-long-random-secret'
export AMIG_TLS_CERTFILE=/etc/amig/fullchain.pem
export AMIG_TLS_KEYFILE=/etc/amig/privkey.pem
amig --host 0.0.0.0
```

Connect an IRC client, enable TLS when configured, provide the server password, and join `#meshtastic-ctrl`. Type `HELP` for the command list.

## Commands

- `SEND <message>` — broadcast a text message.
- `DM <node> <message>` — send a reliable direct message and report ACK/NAK.
- `ALARM <message>` — send a high-priority Meshtastic alert packet.
- `PING <node>` — use Meshtastic `REPLY_APP` to request an echo.
- `NODES`, `INFO <node>`, `LOCATION`, `STATS`, `TIME` — inspect gateway state.
- `WEATHER` — query OpenWeatherMap when configured.
- `HFCONDITIONS` — query current NOAA SWPC Kp, solar flux, and scale products.

Node arguments accept a node ID, number, exact short name, or exact long name. Quote names containing spaces.

More detail is available in [the documentation](docs/index.md).

## Service operation

Run AMIG under a supervisor such as systemd with automatic restart, a dedicated unprivileged account, restricted access to the serial device or TCP radio, and logs captured by the service manager. Keep TLS private-key permissions limited to that account. Validate the deployment with `amig --mock` locally before attaching a radio.

## License and contact

Copyright Akita Engineering. Licensed under GPL-3.0-only; see [LICENSE](LICENSE).

- Website: https://www.akitaengineering.com
- Email: info@akitaengineering.com
- Issues: https://github.com/AkitaEngineering/Akita-Meshtastic-IRC-Gateway/issues
