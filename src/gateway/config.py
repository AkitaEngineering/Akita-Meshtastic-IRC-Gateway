"""Environment-backed defaults for the Akita Meshtastic IRC Gateway."""

from __future__ import annotations

import logging
import os


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _env_float(name: str, default: float, minimum: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


IRC_SERVER_HOST = os.getenv("AMIG_IRC_HOST", "127.0.0.1")
IRC_SERVER_PORT = _env_int("AMIG_IRC_PORT", 6667, 1, 65535)
IRC_SERVER_NAME = os.getenv("AMIG_IRC_SERVER_NAME", "amig.gw")
IRC_PASSWORD = os.getenv("AMIG_IRC_PASSWORD") or None
CONTROL_CHANNEL = os.getenv("AMIG_CONTROL_CHANNEL", "#meshtastic-ctrl")
TLS_CERTFILE = os.getenv("AMIG_TLS_CERTFILE") or None
TLS_KEYFILE = os.getenv("AMIG_TLS_KEYFILE") or None
IRC_MAX_CLIENTS = _env_int("AMIG_IRC_MAX_CLIENTS", 100, 1, 10_000)
IRC_REGISTRATION_TIMEOUT = _env_float("AMIG_IRC_REGISTRATION_TIMEOUT", 30.0, 1.0)

DEFAULT_MESH_CHANNEL_INDEX = _env_int("AMIG_MESH_CHANNEL", 0, 0, 7)
MESH_DEVICE_PORT = os.getenv("AMIG_MESH_DEVICE_PORT") or None
MESH_DEVICE_HOST = os.getenv("AMIG_MESH_DEVICE_HOST") or None
MESH_CONNECT_RETRIES = _env_int("AMIG_MESH_CONNECT_RETRIES", 3, 1, 20)
MESH_CONNECT_TIMEOUT = _env_int("AMIG_MESH_CONNECT_TIMEOUT", 60, 5, 600)
MESH_RETRY_DELAY = _env_float("AMIG_MESH_RETRY_DELAY", 2.0, 0.0)
MESH_SEND_INTERVAL = _env_float("AMIG_MESH_SEND_INTERVAL", 1.0, 0.0)
MESH_RESPONSE_TIMEOUT = _env_float("AMIG_MESH_RESPONSE_TIMEOUT", 30.0, 1.0)

LOG_LEVEL_NAME = os.getenv("AMIG_LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, None)
if not isinstance(LOG_LEVEL, int):
    raise ValueError(f"AMIG_LOG_LEVEL is invalid: {LOG_LEVEL_NAME}")
LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY") or None
WEATHER_LOCATION = os.getenv("WEATHER_LOCATION", "Port Colborne,CA").strip() or None
WEATHER_UNITS = os.getenv("WEATHER_UNITS", "metric").lower()
if WEATHER_UNITS not in {"metric", "imperial", "standard"}:
    raise ValueError("WEATHER_UNITS must be metric, imperial, or standard")

HF_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
HF_FLUX_URL = "https://services.swpc.noaa.gov/products/10cm-flux-30-day.json"
HF_SCALES_URL = "https://services.swpc.noaa.gov/products/noaa-scales.json"


def validate() -> None:
    """Validate settings whose correctness depends on multiple values."""
    if MESH_DEVICE_PORT and MESH_DEVICE_HOST:
        raise ValueError("set only one of AMIG_MESH_DEVICE_PORT and AMIG_MESH_DEVICE_HOST")
    if not CONTROL_CHANNEL.startswith("#") or len(CONTROL_CHANNEL.encode("utf-8")) > 50:
        raise ValueError("AMIG_CONTROL_CHANNEL must begin with '#' and be at most 50 UTF-8 bytes")
    if not IRC_SERVER_NAME or any(char.isspace() for char in IRC_SERVER_NAME):
        raise ValueError("AMIG_IRC_SERVER_NAME must be non-empty and contain no whitespace")
    if bool(TLS_CERTFILE) != bool(TLS_KEYFILE):
        raise ValueError("AMIG_TLS_CERTFILE and AMIG_TLS_KEYFILE must be configured together")


validate()
