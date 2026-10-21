"""The same Tango device serves both standard sources; all I/O is fake."""
import importlib
import json
from types import SimpleNamespace

from tests.unit.test_acq_standard_telemetry import state, signed, KEY
from tests.web.test_acq_telemetry_api import setup_api, URL, api
from legacy.xp_acq_control.elyse_agent.native_telemetry import standard_packet, BANKS
from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkStore


def test_all_27_banks_reach_existing_route_without_a_second_projection(setup_api):
    app, content, calls = setup_api
    sink = TelemetrySinkStore(KEY, permitted_producer_kind="python_acquisition")
    sink.accept(signed(standard_packet(state(), 1)))
    content.clear(); content.update(sink.snapshot())
    body = app.test_client().get(URL).json
    assert body["source"] == "python_daqmx_acquisition"
    assert body["quality"] == "INCOMPLETE"  # Coverage, not fake all-bank readiness.
    assert len(body["snapshot"]["publications"]) == 27
    assert len(body["unavailable_banks"]) == 15
    assert body["snapshot"]["publications"]["C1NI6071E"]["data"] == [123.] * 64
    assert body["snapshot"]["publications"]["EPS"]["data"] is None
    assert body["snapshot"]["publications"]["C9NI6703"]["data"] == [6.5] * 10
    control = importlib.import_module("acq_control_api")
    assert control.DEVICE == api.DEVICE
    assert calls[0] == ("proxy", control.DEVICE)


def test_stale_python_stream_cannot_show_labview_or_fresh_synthetic_statuses(setup_api):
    app, content, calls = setup_api
    sink = TelemetrySinkStore(KEY, permitted_producer_kind="python_acquisition")
    sink.accept(signed(standard_packet(state(), 1)))
    content.clear(); content.update(sink.snapshot())
    for bank in content["publications"].values(): bank["age_seconds"] = 2.1
    body = app.test_client().get(URL).json
    assert body["quality"] == "STALE" and body["source"] == "python_daqmx_acquisition"
    assert len(body["stale_banks"]) == 27
    assert body["snapshot"]["publications"]["EPS"]["data"] is None
