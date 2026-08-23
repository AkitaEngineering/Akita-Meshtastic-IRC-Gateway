from __future__ import annotations

import datetime

import pytest

from gateway.commands.cmd_hfconditions import parse_swpc_products
from gateway.commands.cmd_weather import _local_api_time
from gateway.main import initialize_meshtastic_interface, parse_args
from gateway.server import MockMeshtasticInterface


def test_swpc_parser_uses_latest_observations():
    parsed = parse_swpc_products(
        [
            {"time_tag": "2026-01-01T00:00:00", "Kp": 2.0},
            {"time_tag": "2026-01-01T03:00:00", "Kp": 4.33},
        ],
        [
            {"time_tag": "2026-01-01T20:00:00", "flux": 120},
            {"time_tag": "2026-01-02T20:00:00", "flux": 130},
        ],
        {"0": {"R": {"Scale": "0"}}, "1": {"R": {"MinorProb": "25"}}},
    )
    assert parsed["kp"]["Kp"] == 4.33
    assert parsed["flux"]["flux"] == 130
    assert parsed["forecast"]["R"]["MinorProb"] == "25"


def test_swpc_parser_rejects_wrong_schema():
    with pytest.raises((TypeError, ValueError)):
        parse_swpc_products({}, [], {})


def test_weather_timestamp_uses_location_offset():
    timestamp = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc).timestamp()
    assert _local_api_time(timestamp, -5 * 3600) == "2025-12-31 19:00:00 -0500"


def test_mock_mode_is_explicit_and_argument_validation_is_strict():
    args = parse_args(["--mock", "--mesh-channel", "7"])
    assert args.mock is True
    assert isinstance(initialize_meshtastic_interface(None, None, use_mock=True), MockMeshtasticInterface)
    with pytest.raises(SystemExit):
        parse_args(["--mock", "--mesh-channel", "8"])


def test_real_mode_requires_a_connection_target():
    with pytest.raises(RuntimeError, match="configure --mesh-port"):
        initialize_meshtastic_interface(None, None, use_mock=False)
