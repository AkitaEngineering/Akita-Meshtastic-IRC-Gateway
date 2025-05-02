# src/gateway/commands/cmd_hfconditions.py

"""
Command module for handling the 'HFCONDITIONS' command. Fetches data from NOAA SWPC.
"""

import logging
import requests # For making HTTP requests
import json     # For parsing JSON response
from datetime import datetime, timezone # For parsing ISO timestamps

# Import config settings
try:
    from gateway.config import HF_DATA_SOURCE_URL
except ImportError:
    logging.error("Failed to import HF config from gateway.config")
    # Fallback URL if config import fails
    HF_DATA_SOURCE_URL = "https://services.swpc.noaa.gov/products/summary/3-day-forecast.json"

COMMAND_NAME = "HFCONDITIONS"
COMMAND_HELP = "HFCONDITIONS - Shows current Solar/HF propagation indicators (NOAA SWPC)"

def parse_swpc_summary(data):
    """
    Parses the NOAA SWPC 3-day forecast JSON data.
    Returns a dictionary with key indicators or None if parsing fails.
    Focuses on the *current* or most recent data available in the forecast structure.
    """
    if not isinstance(data, list) or not data:
        logging.warning("SWPC summary data is not a non-empty list.")
        return None

    # Find the most recent forecast entry based on issue time
    latest_summary = None
    latest_ts = 0
    for entry in data:
        if isinstance(entry, dict) and 'issue_datetime' in entry:
            try:
                # Parse ISO 8601 timestamp, handle potential 'Z' for UTC
                ts_str = entry['issue_datetime'].replace('Z', '+00:00')
                entry_ts = datetime.fromisoformat(ts_str).timestamp()
                if entry_ts > latest_ts:
                    latest_ts = entry_ts
                    latest_summary = entry
            except ValueError:
                logging.warning(f"Could not parse timestamp: {entry['issue_datetime']}")
                continue # Skip entry with bad timestamp

    if not latest_summary:
        logging.warning("Could not find a valid summary entry with an issue_datetime.")
        return None

    summary = latest_summary
    logging.debug(f"Using SWPC summary issued at: {summary.get('issue_datetime')}")

    try:
        # Extract relevant fields - keys might change, refer to SWPC product docs
        # Kp Index: Often provided as a list for different periods (e.g., 3hr, 6hr)
        # We'll try to get the most recent *observed* Kp if available, else forecast
        kp_index = summary.get('kp_index', summary.get('kp', 'N/A')) # Check common keys
        if isinstance(kp_index, list) and kp_index:
            kp_index = kp_index[-1] # Assume last value is most recent observation/forecast

        # Solar Flux (F10.7cm)
        solar_flux = summary.get('10cm_flux', summary.get('f107', 'N/A'))
        if isinstance(solar_flux, list) and solar_flux: # Sometimes flux is forecast per day
             solar_flux = solar_flux[0] # Take the first day's forecast/value

        # Radio Blackout forecast (R scale) - Often forecast per day
        r_scale_fcst = summary.get('r_scale_forecast', summary.get('radio_blackout', 'N/A'))
        if isinstance(r_scale_fcst, list) and r_scale_fcst:
             r_scale_fcst = r_scale_fcst[0] # Take first day's forecast

        # Geomagnetic Storm forecast (G scale) - Often forecast per day
        g_scale_fcst = summary.get('g_scale_forecast', summary.get('geomagnetic_storm', 'N/A'))
        if isinstance(g_scale_fcst, list) and g_scale_fcst:
             g_scale_fcst = g_scale_fcst[0] # Take first day's forecast

        # Solar Radiation Storm forecast (S scale) - Often forecast per day
        s_scale_fcst = summary.get('s_scale_forecast', summary.get('solar_radiation_storm', 'N/A'))
        if isinstance(s_scale_fcst, list) and s_scale_fcst:
             s_scale_fcst = s_scale_fcst[0] # Take first day's forecast

        # Extract issue time
        issue_time_str = summary.get('issue_datetime', 'Unknown Time')
        # Format issue time nicely
        try:
            issue_dt = datetime.fromisoformat(issue_time_str.replace('Z', '+00:00'))
            issue_time_fmt = issue_dt.strftime('%Y-%m-%d %H:%M Z')
        except ValueError:
            issue_time_fmt = issue_time_str # Fallback to original string

        return {
            "issue_time": issue_time_fmt,
            "kp_index": kp_index,
            "solar_flux": solar_flux,
            "radio_blackout": r_scale_fcst,
            "geomagnetic_storm": g_scale_fcst,
            "solar_rad_storm": s_scale_fcst,
        }
    except Exception as e:
        logging.error(f"Error parsing SWPC summary data structure: {e}", exc_info=True)
        return None


def execute(server, connection, nick, args):
    """
    Executes the HFCONDITIONS command by fetching data from NOAA SWPC.

    Args:
        server: The MeshtasticGatewayServer instance.
        connection: The IRC connection object for the client.
        nick: The nickname of the user issuing the command.
        args: A list of strings (should be empty).
    """
    if not HF_DATA_SOURCE_URL:
        connection.notice(nick, "HF Conditions command is not configured (data source URL missing).")
        logging.warning("HFCONDITIONS command executed but not configured.")
        return

    connection.notice(nick, "Fetching HF conditions from NOAA SWPC...")

    try:
        # Set a user-agent to identify the client
        headers = {'User-Agent': 'AkitaMeshtasticIRCGateway/0.1 (info@akitaengineering.com)'}
        response = requests.get(HF_DATA_SOURCE_URL, headers=headers, timeout=15) # 15 second timeout
        response.raise_for_status() # Raise HTTPError for bad responses

        # Parse the JSON response
        try:
            data = response.json()
            logging.debug(f"NOAA SWPC API response: {data}")
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON response from SWPC: {e}")
            connection.notice(nick, "Error: Received invalid data format from SWPC.")
            return

        # Parse the relevant data from the JSON structure
        parsed_data = parse_swpc_summary(data)

        if parsed_data:
            # Format and send the data to IRC
            connection.notice(nick, f"--- HF Conditions (Source: NOAA SWPC @ {parsed_data['issue_time']}) ---")
            connection.notice(nick, f"Solar Flux (10.7cm): {parsed_data['solar_flux']}")
            connection.notice(nick, f"Planetary K-Index (Kp): {parsed_data['kp_index']}")
            # Provide context for Kp index
            try:
                # Kp index can be float in some products, handle gracefully
                kp_val = int(float(parsed_data['kp_index']))
                if kp_val <= 1: kp_desc = "Inactive"
                elif kp_val == 2: kp_desc = "Quiet"
                elif kp_val == 3: kp_desc = "Unsettled"
                elif kp_val == 4: kp_desc = "Active"
                elif kp_val == 5: kp_desc = "Minor Storm"
                elif kp_val == 6: kp_desc = "Major Storm"
                elif kp_val >= 7: kp_desc = "Severe/Extreme Storm"
                else: kp_desc = "Unknown"
                connection.notice(nick, f"Geomagnetic Activity: {kp_desc} (Kp={kp_val})")
            except (ValueError, TypeError):
                 connection.notice(nick, f"Geomagnetic Activity: N/A (Kp={parsed_data['kp_index']})") # Show raw value if not parseable

            # Display forecasts if available (often forecast for next 24-72hrs)
            connection.notice(nick, "--- Forecasts (Next ~24hrs) ---")
            if parsed_data['radio_blackout'] != 'N/A':
                connection.notice(nick, f"Radio Blackout (R): {parsed_data['radio_blackout']}")
            if parsed_data['geomagnetic_storm'] != 'N/A':
                connection.notice(nick, f"Geomagnetic Storm (G): {parsed_data['geomagnetic_storm']}")
            if parsed_data['solar_rad_storm'] != 'N/A':
                connection.notice(nick, f"Solar Radiation Storm (S): {parsed_data['solar_rad_storm']}")

            connection.notice(nick, "--- End of HF Conditions ---")
        else:
            connection.notice(nick, "Error: Could not parse relevant data from SWPC response.")


    except requests.exceptions.Timeout:
        logging.error("NOAA SWPC request timed out.")
        connection.notice(nick, "Error: Request to NOAA SWPC timed out.")
    except requests.exceptions.HTTPError as e:
        logging.error(f"NOAA SWPC HTTP error: {e.response.status_code} - {e.response.text}")
        connection.notice(nick, f"Error: NOAA SWPC returned status code {e.response.status_code}.")
    except requests.exceptions.RequestException as e:
        logging.error(f"NOAA SWPC request failed: {e}", exc_info=True)
        connection.notice(nick, f"Error fetching HF conditions data: Network or connection issue.")
    except Exception as e:
        logging.error(f"Error processing HF conditions data: {e}", exc_info=True)
        connection.notice(nick, "Error processing HF conditions data.")

