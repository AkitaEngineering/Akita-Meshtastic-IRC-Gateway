"""HFCONDITIONS command backed by current NOAA SWPC JSON products."""

import concurrent.futures
import datetime
import logging
import threading
import time
from collections.abc import Mapping

import requests

from gateway import config

COMMAND_NAME = "HFCONDITIONS"
COMMAND_HELP = "HFCONDITIONS - Shows current NOAA solar and geomagnetic indicators"
_CACHE_TTL = 300.0
_cache_lock = threading.Lock()
_cache: tuple[float, dict] | None = None


def _timestamp(value):
    if not isinstance(value, str):
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or datetime.timezone.utc)
    except ValueError:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def parse_swpc_products(kp_data, flux_data, scales_data):
    if not isinstance(kp_data, list) or not isinstance(flux_data, list) or not isinstance(scales_data, Mapping):
        raise ValueError("unexpected NOAA response schema")
    valid_kp = [row for row in kp_data if isinstance(row, Mapping) and isinstance(row.get("Kp"), (int, float))]
    valid_flux = [row for row in flux_data if isinstance(row, Mapping) and isinstance(row.get("flux"), (int, float))]
    current_scales = scales_data.get("0")
    forecast = scales_data.get("1")
    if not valid_kp or not valid_flux or not isinstance(current_scales, Mapping):
        raise ValueError("NOAA response is missing current observations")
    kp = max(valid_kp, key=lambda row: _timestamp(row.get("time_tag")))
    flux = max(valid_flux, key=lambda row: _timestamp(row.get("time_tag")))
    return {
        "kp": kp,
        "flux": flux,
        "scales": current_scales,
        "forecast": forecast if isinstance(forecast, Mapping) else {},
    }


def _get_json(url):
    response = requests.get(
        url,
        headers={"User-Agent": "Akita-Meshtastic-IRC-Gateway/1.0 (info@akitaengineering.com)"},
        timeout=(3.05, 10),
    )
    response.raise_for_status()
    return response.json()


def _fetch_conditions():
    global _cache
    with _cache_lock:
        if _cache and time.monotonic() - _cache[0] < _CACHE_TTL:
            return _cache[1]
    urls = (config.HF_KP_URL, config.HF_FLUX_URL, config.HF_SCALES_URL)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="swpc") as executor:
        kp_data, flux_data, scales_data = executor.map(_get_json, urls)
    parsed = parse_swpc_products(kp_data, flux_data, scales_data)
    with _cache_lock:
        _cache = (time.monotonic(), parsed)
    return parsed


def _scale(entry):
    if not isinstance(entry, Mapping):
        return "N/A"
    scale = entry.get("Scale")
    text = entry.get("Text")
    if scale is None:
        return "N/A"
    return f"{scale} ({text or 'no description'})"


def _kp_description(value):
    if value < 2:
        return "quiet"
    if value < 4:
        return "unsettled"
    if value < 5:
        return "active"
    if value < 6:
        return "minor storm"
    if value < 7:
        return "moderate storm"
    if value < 8:
        return "strong storm"
    if value < 9:
        return "severe storm"
    return "extreme storm"


def execute(server, connection, nick, args):
    if args:
        connection.notice(nick, f"Usage: {COMMAND_HELP}")
        return
    try:
        data = _fetch_conditions()
        kp = data["kp"]
        flux = data["flux"]
        scales = data["scales"]
        forecast = data["forecast"]
        kp_value = float(kp["Kp"])
        observed = _timestamp(kp.get("time_tag")).strftime("%Y-%m-%d %H:%M UTC")
        flux_time = _timestamp(flux.get("time_tag")).strftime("%Y-%m-%d %H:%M UTC")
        connection.notice(nick, f"--- HF Conditions (NOAA SWPC; Kp observed {observed}) ---")
        connection.notice(nick, f"Planetary Kp: {kp_value:.2f} ({_kp_description(kp_value)})")
        connection.notice(nick, f"10.7 cm solar flux: {float(flux['flux']):.0f} sfu (observed {flux_time})")
        connection.notice(
            nick,
            f"Current NOAA scales: R{_scale(scales.get('R'))} | S{_scale(scales.get('S'))} | G{_scale(scales.get('G'))}",
        )
        r_forecast = forecast.get("R") if isinstance(forecast.get("R"), Mapping) else {}
        s_forecast = forecast.get("S") if isinstance(forecast.get("S"), Mapping) else {}
        connection.notice(
            nick,
            f"Today forecast probabilities: R1-R2 {r_forecast.get('MinorProb', 'N/A')}% | "
            f"R3-R5 {r_forecast.get('MajorProb', 'N/A')}% | S1+ {s_forecast.get('Prob', 'N/A')}%",
        )
    except requests.Timeout:
        connection.notice(nick, "NOAA SWPC timed out.")
    except (requests.RequestException, ValueError, KeyError, TypeError):
        logging.exception("NOAA SWPC request or response processing failed")
        connection.notice(nick, "HF conditions are temporarily unavailable.")
