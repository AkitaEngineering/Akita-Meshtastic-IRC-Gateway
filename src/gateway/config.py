# src/gateway/config.py

"""
Configuration settings for the Akita Meshtastic IRC Gateway (AMIG).

Modify the values in this file to customize the gateway's behavior.
Command-line arguments can override some of these settings.
"""

import logging
import os # Used for API key environment variable fallback

# --- IRC Server Settings ---
IRC_SERVER_HOST: str = "0.0.0.0"       # IP address to bind the IRC server to
IRC_SERVER_PORT: int = 6667            # Port for the IRC server
IRC_SERVER_NAME: str = "amig.gw"       # Default name reported by the IRC server
CONTROL_CHANNEL: str = "#meshtastic-ctrl" # Default IRC channel for commands/control

# --- Meshtastic Settings ---
DEFAULT_MESH_CHANNEL_INDEX: int = 0    # Default Meshtastic channel index for SEND/ALARM (0 is usually Primary)
# Set one of the following for your Meshtastic device connection, or use command-line args.
# Leave as None to default to command-line args or the Mock Interface if no args are given.
MESH_DEVICE_PORT: str | None = None      # e.g., "/dev/ttyUSB0", "COM3"
MESH_DEVICE_HOST: str | None = None      # e.g., "192.168.1.100"
# Timeout in seconds for Meshtastic operations where applicable (e.g., awaiting reply)
# Note: Actual timeouts are often handled internally by the library/pubsub
MESH_ACK_TIMEOUT: float = 30.0         # Example: Timeout for waiting for an ACK

# --- Logging Settings ---
LOG_LEVEL = logging.INFO               # Default logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_FORMAT: str = '%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
LOG_DATE_FORMAT: str = '%Y-%m-%d %H:%M:%S'

# --- External Service Settings ---

# Weather Command (OpenWeatherMap)
# Get a free API key from https://openweathermap.org/appid
# You can set the key directly here, or preferably use an environment variable WEATHER_API_KEY
WEATHER_API_KEY: str | None = os.environ.get("WEATHER_API_KEY") or None # SET YOUR API KEY HERE or via environment variable
# Location for weather forecast (e.g., "City,CountryCode", "lat=xxx&lon=yyy", zip=...)
# See https://openweathermap.org/current#builtin
WEATHER_LOCATION: str | None = "Port Colborne,CA" # SET YOUR LOCATION HERE
WEATHER_UNITS: str = "metric" # 'metric' for Celsius, 'imperial' for Fahrenheit

# HF Conditions Command (NOAA SWPC)
# Using the 3-day forecast JSON product
HF_DATA_SOURCE_URL: str | None = "https://services.swpc.noaa.gov/products/summary/3-day-forecast.json"

# --- Validate Configuration (Basic) ---
# You could add more complex validation here if needed
if not isinstance(IRC_SERVER_PORT, int) or not (1024 <= IRC_SERVER_PORT <= 65535):
    logging.warning(f"IRC_SERVER_PORT ({IRC_SERVER_PORT}) is outside the recommended range (1024-65535). Check permissions for ports < 1024.")

if MESH_DEVICE_PORT and MESH_DEVICE_HOST:
    logging.warning("Both MESH_DEVICE_PORT and MESH_DEVICE_HOST are set in config.py. Command-line args or --mesh-port will take precedence.")

if not WEATHER_API_KEY:
    logging.warning("WEATHER_API_KEY is not set in config.py or environment variables. The WEATHER command will not function.")
if not WEATHER_LOCATION:
    logging.warning("WEATHER_LOCATION is not set in config.py. The WEATHER command will not function.")


logging.info("Configuration loaded from config.py")
