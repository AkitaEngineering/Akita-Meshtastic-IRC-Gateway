# Installation

AMIG requires Python 3.10 or newer and access to either a Meshtastic serial device or a Meshtastic TCP endpoint.

```bash
git clone https://github.com/AkitaEngineering/Akita-Meshtastic-IRC-Gateway.git
cd Akita-Meshtastic-IRC-Gateway
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Windows PowerShell activation is `.venv\Scripts\Activate.ps1`.

Configure one radio transport:

```bash
export AMIG_MESH_DEVICE_PORT=/dev/ttyACM0
# or
export AMIG_MESH_DEVICE_HOST=192.168.1.100
```

The process will stop if neither transport is configured. Use `amig --mock` only for an explicit local test.

For the optional weather command:

```bash
export WEATHER_API_KEY=your_openweathermap_key
export WEATHER_LOCATION='Port Colborne,CA'
export WEATHER_UNITS=metric
```

Install documentation tooling with `python -m pip install '.[docs]'` and build it with `mkdocs build --strict`.
