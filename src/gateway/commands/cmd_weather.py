# src/gateway/commands/cmd_weather.py

"""
Command module for handling the 'WEATHER' command. Fetches data from OpenWeatherMap.
"""

import logging
import requests # For making HTTP requests
import datetime
import time # For sunrise/sunset formatting

# Import config settings
try:
    from gateway.config import WEATHER_API_KEY, WEATHER_LOCATION, WEATHER_UNITS
except ImportError:
    logging.error("Failed to import weather config from gateway.config")
    WEATHER_API_KEY = None
    WEATHER_LOCATION = None
    WEATHER_UNITS = "metric"

COMMAND_NAME = "WEATHER"
COMMAND_HELP = "WEATHER - Shows current weather conditions (OpenWeatherMap)"

# OpenWeatherMap API endpoint for current weather
API_URL = "https://api.openweathermap.org/data/2.5/weather"

def execute(server, connection, nick, args):
    """
    Executes the WEATHER command by fetching data from OpenWeatherMap.

    Args:
        server: The MeshtasticGatewayServer instance.
        connection: The IRC connection object for the client.
        nick: The nickname of the user issuing the command.
        args: A list of strings (should be empty).
    """
    if not WEATHER_API_KEY or not WEATHER_LOCATION:
        connection.notice(nick, "Weather command is not configured (API key or location missing in config.py).")
        logging.warning("WEATHER command executed but not configured.")
        return

    connection.notice(nick, f"Fetching weather for {WEATHER_LOCATION}...")

    params = {
        'q': WEATHER_LOCATION,
        'appid': WEATHER_API_KEY,
        'units': WEATHER_UNITS
    }

    try:
        # Make the API request with a timeout
        response = requests.get(API_URL, params=params, timeout=10) # 10 second timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        data = response.json()
        logging.debug(f"OpenWeatherMap API response: {data}")

        # --- Parse Current Weather Data ---
        if 'main' in data and 'weather' in data and data['weather']:
            main = data['main']
            weather_list = data['weather']
            weather = weather_list[0] # Use the primary weather condition
            wind = data.get('wind', {})
            sys_info = data.get('sys', {})
            location_name = data.get('name', WEATHER_LOCATION)
            dt_ts = data.get('dt') # Timestamp of data calculation

            temp = main.get('temp')
            feels_like = main.get('feels_like')
            humidity = main.get('humidity')
            pressure = main.get('pressure')
            description = weather.get('description', 'N/A').capitalize()
            wind_speed = wind.get('speed')
            wind_deg = wind.get('deg')
            sunrise_ts = sys_info.get('sunrise')
            sunset_ts = sys_info.get('sunset')

            # Determine units suffix based on config
            unit_suffix = "°C" if WEATHER_UNITS == 'metric' else "°F"
            speed_suffix = "m/s" if WEATHER_UNITS == 'metric' else "mph" # OWM uses m/s by default

            # Format output strings safely, handling None values
            temp_str = f"{temp:.1f}{unit_suffix}" if isinstance(temp, (int, float)) else "N/A"
            feels_str = f"{feels_like:.1f}{unit_suffix}" if isinstance(feels_like, (int, float)) else "N/A"
            humidity_str = f"{humidity}%" if isinstance(humidity, (int, float)) else "N/A"
            pressure_str = f"{pressure} hPa" if isinstance(pressure, (int, float)) else "N/A"
            wind_str = f"{wind_speed:.1f}{speed_suffix}" if isinstance(wind_speed, (int, float)) else "N/A"
            if isinstance(wind_deg, (int, float)): wind_str += f" ({wind_deg}°)" # Add direction degrees

            # Format timestamps using local time
            sunrise_str = time.strftime('%H:%M', time.localtime(sunrise_ts)) if sunrise_ts else "N/A"
            sunset_str = time.strftime('%H:%M', time.localtime(sunset_ts)) if sunset_ts else "N/A"
            report_time_str = time.strftime('%H:%M:%S %Z', time.localtime(dt_ts)) if dt_ts else "N/A"


            # Send formatted weather info to IRC
            connection.notice(nick, f"--- Weather for {location_name} (as of {report_time_str}) ---")
            connection.notice(nick, f"Conditions: {description}")
            connection.notice(nick, f"Temperature: {temp_str} (Feels like: {feels_str})")
            connection.notice(nick, f"Humidity: {humidity_str} | Pressure: {pressure_str}")
            connection.notice(nick, f"Wind: {wind_str}")
            connection.notice(nick, f"Sunrise: {sunrise_str} | Sunset: {sunset_str}")
            connection.notice(nick, "--- End of Weather ---")

        else:
            logging.error(f"Unexpected API response format from OpenWeatherMap: {data}")
            connection.notice(nick, "Error: Received unexpected data format from weather API.")

    except requests.exceptions.Timeout:
        logging.error("Weather API request timed out.")
        connection.notice(nick, "Error: Request to weather API timed out.")
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        logging.error(f"Weather API HTTP error: {status_code} - {e.response.text}")
        if status_code == 401:
            connection.notice(nick, "Error: Invalid weather API key.")
        elif status_code == 404:
            connection.notice(nick, f"Error: Weather location '{WEATHER_LOCATION}' not found.")
        elif status_code == 429:
            connection.notice(nick, "Error: Weather API rate limit exceeded.")
        else:
            connection.notice(nick, f"Error: Weather API returned status code {status_code}.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Weather API request failed: {e}", exc_info=True)
        connection.notice(nick, f"Error fetching weather data: Network or connection issue.")
    except Exception as e:
        logging.error(f"Error processing weather data: {e}", exc_info=True)
        connection.notice(nick, "Error processing weather data.")

