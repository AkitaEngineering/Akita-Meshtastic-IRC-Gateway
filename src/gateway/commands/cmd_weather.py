"""WEATHER command backed by OpenWeatherMap's current-weather API."""

import datetime
import logging
import threading
import time
from collections.abc import Mapping

import requests

from gateway import config

COMMAND_NAME = "WEATHER"
COMMAND_HELP = "WEATHER - Shows configured-location current weather (OpenWeatherMap)"
API_URL = "https://api.openweathermap.org/data/2.5/weather"
_CACHE_TTL = 300.0
_cache_lock = threading.Lock()
_cache: tuple[float, dict] | None = None


def _fetch_weather() -> dict:
    global _cache
    with _cache_lock:
        if _cache and time.monotonic() - _cache[0] < _CACHE_TTL:
            return _cache[1]
    response = requests.get(
        API_URL,
        params={"q": config.WEATHER_LOCATION, "appid": config.WEATHER_API_KEY, "units": config.WEATHER_UNITS},
        headers={"User-Agent": "Akita-Meshtastic-IRC-Gateway/1.0"},
        timeout=(3.05, 10),
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("weather API returned a non-object response")
    with _cache_lock:
        _cache = (time.monotonic(), data)
    return data


def _local_api_time(timestamp, offset_seconds):
    if not isinstance(timestamp, (int, float)):
        return "N/A"
    offset = int(offset_seconds) if isinstance(offset_seconds, (int, float)) else 0
    zone = datetime.timezone(datetime.timedelta(seconds=offset))
    return datetime.datetime.fromtimestamp(timestamp, tz=zone).strftime("%Y-%m-%d %H:%M:%S %z")


def execute(server, connection, nick, args):
    if args:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return
    if not config.WEATHER_API_KEY or not config.WEATHER_LOCATION:
        connection.notice(nick, "WEATHER is disabled; configure WEATHER_API_KEY and WEATHER_LOCATION.")
        return
    try:
        data = _fetch_weather()
        main = data.get("main")
        conditions = data.get("weather")
        if not isinstance(main, Mapping) or not isinstance(conditions, list) or not conditions:
            raise ValueError("weather response is missing required fields")
        condition = conditions[0] if isinstance(conditions[0], Mapping) else {}
        wind = data.get("wind") if isinstance(data.get("wind"), Mapping) else {}
        system = data.get("sys") if isinstance(data.get("sys"), Mapping) else {}
        offset = data.get("timezone", 0)

        if config.WEATHER_UNITS == "metric":
            temperature_unit, speed_unit = "°C", "m/s"
        elif config.WEATHER_UNITS == "imperial":
            temperature_unit, speed_unit = "°F", "mph"
        else:
            temperature_unit, speed_unit = "K", "m/s"

        def number(value, suffix, decimals=1):
            return f"{value:.{decimals}f}{suffix}" if isinstance(value, (int, float)) else "N/A"

        wind_text = number(wind.get("speed"), speed_unit)
        if isinstance(wind.get("deg"), (int, float)):
            wind_text += f" at {wind['deg']:.0f}°"
        connection.notice(
            nick,
            f"--- Weather for {data.get('name') or config.WEATHER_LOCATION} "
            f"(as of {_local_api_time(data.get('dt'), offset)}) ---",
        )
        connection.notice(nick, f"Conditions: {str(condition.get('description', 'N/A')).capitalize()}")
        connection.notice(
            nick,
            f"Temperature: {number(main.get('temp'), temperature_unit)} "
            f"(feels like {number(main.get('feels_like'), temperature_unit)})",
        )
        connection.notice(
            nick,
            f"Humidity: {number(main.get('humidity'), '%', 0)} | Pressure: {number(main.get('pressure'), ' hPa', 0)}",
        )
        connection.notice(nick, f"Wind: {wind_text}")
        connection.notice(
            nick,
            f"Sunrise: {_local_api_time(system.get('sunrise'), offset)} | "
            f"Sunset: {_local_api_time(system.get('sunset'), offset)}",
        )
    except requests.Timeout:
        connection.notice(nick, "Weather service timed out.")
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        logging.warning("Weather HTTP failure: %s", status)
        messages = {
            401: "Weather API credentials were rejected.",
            404: "Configured weather location was not found.",
            429: "Weather API rate limit exceeded.",
        }
        connection.notice(nick, messages.get(status, f"Weather service returned HTTP {status}."))
    except (requests.RequestException, ValueError):
        logging.exception("Weather request or response processing failed")
        connection.notice(nick, "Weather data is temporarily unavailable.")
