"""Read only the fixed Everest telemetry receiver. No XP, NI or PSP access."""

import json
import os
import math
from datetime import datetime, timezone

import tango_gateway
from flask import Blueprint, current_app, jsonify, request, Response
from pathlib import Path
from legacy.xp_acq_agent.elyse_agent.shared_state import BANKS
from mutation_auth import install_mutation_auth
from acq_contract import DEVICE, XP_HOST, TANGO_DEVICE, topology
from acq_supervision_counter import project_counter
from acq_camera_broker import gzip_events

MAX_JSON_BYTES = 2 * 1024 * 1024
STALE_SECONDS = 2
acq_telemetry_api = Blueprint(
    "acq_telemetry_api", __name__, url_prefix="/api/elyse/acquisition/telemetry"
)
install_mutation_auth(acq_telemetry_api, protected_get_endpoints=(
    "get_telemetry", "get_cooling_safety", "get_history", "get_archive_status", "get_history_view",
    "get_orchestrators", "get_raw_video", "get_video_channels", "get_video_stream",
    "get_supervision_synchronization"))


@acq_telemetry_api.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def browser_data(value):
    """Preserve integer precision in browsers; never turn unavailable into zero."""
    if type(value) is int and abs(value) > 2**53 - 1:
        return {"integer_decimal": str(value)}
    if isinstance(value, list):
        return [browser_data(item) for item in value]
    if isinstance(value, dict):
        return {key: browser_data(item) for key, item in value.items()}
    return value


def local_history_store():
    # Explicit local deployment configuration, never a request-supplied path.
    # History disk I/O must not hold Tango's live-device request serialization.
    config = current_app.config.get('ELYSE_TELEMETRY_ARCHIVE_CONFIG') or os.environ.get('ELYSE_TELEMETRY_ARCHIVE_CONFIG')
    if not config:
        return None
    from DeviceServers.control.elyse_acq.telemetry_archive import PostgresStore
    return PostgresStore(config, read_timeout_ms=10000)


def present_snapshot(raw, server_state):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("invalid telemetry attribute size")
    snapshot = json.loads(raw)
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("source") not in ("copied_labview_telemetry", "python_daqmx_acquisition", "federated_orchestrators")
        or snapshot.get("hardware_writes") is not False
        or snapshot.get("storage_mode") != "ram_latest"
        or not isinstance(snapshot.get("publications"), dict)
    ):
        raise ValueError("unexpected telemetry receiver contract")
    publications = snapshot["publications"]
    if set(publications) - set(BANKS):
        raise ValueError("unexpected telemetry bank")
    for bank in publications.values():
        if not isinstance(bank, dict):
            raise ValueError("invalid telemetry bank")
        age = bank.get("age_seconds")
        unavailable_age = (snapshot.get("source") == "federated_orchestrators" and age is None
                           and bank.get("data") is None and bank.get("error", {}).get("status") is True
                           and bank.get("error", {}).get("code") == -80001)
        if not unavailable_age and (type(age) not in (int, float) or not math.isfinite(age) or age < 0):
            raise ValueError("invalid telemetry age")
        error = bank.get("error")
        if (
            not isinstance(error, dict)
            or type(error.get("status")) is not bool
            or type(error.get("code")) is not int
            or not isinstance(error.get("source"), str)
        ):
            raise ValueError("invalid bank read error")
        bank["stale"] = unavailable_age or bank.get("stale") is not False or age >= STALE_SECONDS
        bank["data"] = browser_data(bank.get("data"))
    # Strict JSON: a corrupt receiver must not send NaN/Infinity to the browser.
    json.dumps(snapshot, allow_nan=False)
    missing = [name for name in BANKS if name not in publications]
    stale = [name for name, bank in publications.items() if bank["stale"] and bank.get("data") is not None]
    errors = [
        name
        for name, bank in publications.items()
        if bank["error"]["status"] or bank["error"]["code"] != 0
    ]
    unavailable = [name for name in errors if snapshot.get("source") in ("python_daqmx_acquisition", "federated_orchestrators")
                   and (snapshot.get("source") == "federated_orchestrators"
                        or publications[name].get("producer_kind") == "python_acquisition")
                   and publications[name]["error"]["code"] == -80001
                   and publications[name]["data"] is None]
    read_errors = [name for name in errors if name not in unavailable]
    quality = (
        "RECEIVER_NOT_READY"
        if server_state != "ON"
        else "WAITING"
        if not publications
        else "READ_ERROR"
        if read_errors
        else "STALE"
        if stale
        else "INCOMPLETE"
        if missing or unavailable
        else "FRESH"
    )
    return dict(
        schema_version=1,
        execution_allowed=False,
        hardware_writes=False,
        source_host=XP_HOST,
        device=TANGO_DEVICE,
        topology=topology(),
        server_state=server_state,
        observed_utc=datetime.now(timezone.utc).isoformat(),
        stale_after_seconds=STALE_SECONDS,
        expected_banks=list(BANKS),
        quality=quality,
        missing_banks=missing,
        stale_banks=stale,
        error_banks=errors,
        unavailable_banks=unavailable,
        source=snapshot["source"],
        snapshot=snapshot,
        cooling_safety=snapshot.get("cooling_safety"),
        orchestrators=snapshot.get("owners"),
        video_metadata=snapshot.get("video_metadata"),
    )


def _read_observer_attribute(name):
    """Same strict bounded observer read as the active facade; never XP."""
    proxy = tango_gateway.create_device_proxy(DEVICE)
    proxy.set_timeout_millis(1500)
    attribute = proxy.read_attribute(name)
    if attribute.has_failed:
        raise ValueError("Read-only telemetry attribute unavailable")
    return _observer_json(attribute.value)


def _observer_json(raw):
    if type(raw) is not str or not 0 < len(raw.encode("utf-8")) <= MAX_JSON_BYTES:
        raise ValueError("Bounded observer JSON required")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate observer field")
            value[key] = item
        return value
    def nonfinite(unused):
        raise ValueError("Nonfinite observer value")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    if type(value) is not dict:
        raise ValueError("Observer metadata object required")
    return value


def _unsupported_observer(error):
    return isinstance(error, AttributeError) or any(name in str(error) for name in
        ('API_CommandNotFound', 'API_AttrNotFound', 'API_AttributeNotFound'))


def _camera_channel(raw):
    if raw in (None, ''):
        return None
    if not isinstance(raw, str) or not raw.isascii() or not raw.isdecimal():
        raise ValueError('Unsigned camera channel required')
    result = int(raw)
    if not 0 <= result <= 4294967295:
        raise ValueError('Unsigned camera channel required')
    return result


def _present_video(value, channel=None):
    if value.get('owner') != 'supervision' or type(value.get('available')) is not bool:
        raise ValueError('Unexpected video owner')
    if value['available']:
        from acq_video_contract import validate_video_frame
        validate_video_frame(value.get('frame'))
        frame = value['frame']
        if frame is None or any(value.get(key) != frame[key] for key in
                ('capture_session_id', 'sequence', 'width', 'height', 'pixel_type',
                 'encoding', 'channel', 'processing', 'observed_utc', 'source')):
            raise ValueError('Camera envelope does not identify its pixels')
        if channel is not None and channel != frame['channel']:
            raise ValueError('Requested camera channel is not the observed channel')
        age = value.get('age_seconds')
        if type(age) not in (int, float) or not math.isfinite(age) or age < 0:
            raise ValueError('Current camera age required')
    elif value.get('frame') is not None:
        raise ValueError('Unavailable camera cannot contain current pixels')
    return dict(value, schema_version=1, device=TANGO_DEVICE)


def read_camera_source(channel=None):
    """Passive getter on the one DS; old DS fallback has no hardware access."""
    try:
        proxy = tango_gateway.create_device_proxy(DEVICE)
        proxy.set_timeout_millis(1500)
        value = _observer_json(proxy.command_inout('ReadCameraFrame', '' if channel is None else str(channel)))
    except Exception as error:
        if not _unsupported_observer(error):
            raise
        value = _read_observer_attribute('video_json')
    return _present_video(value, channel)


def read_camera_channels():
    try:
        value = _read_observer_attribute('camera_stream_json')
        if (value.get('owner') != 'supervision' or type(value.get('channel_ids')) is not list
                or len(value['channel_ids']) > 8 or any(type(channel) is not int
                    or not 0 <= channel <= 4294967295 for channel in value['channel_ids'])):
            raise ValueError('Actual camera channel metadata required')
        return dict(value, schema_version=1)
    except Exception as error:
        if not _unsupported_observer(error):
            raise
        value = _read_observer_attribute('video_json')
        channel = value.get('channel')
        observed = type(channel) is int and 0 <= channel <= 4294967295
        return dict(schema_version=1, owner='supervision', enabled=False,
                    transport='legacy_sampled_telemetry', channel_ids=[channel] if observed else [],
                    selected_channel=channel if observed else None,
                    channels={str(channel): {key: val for key, val in value.items() if key != 'frame'}} if observed else {})


@acq_telemetry_api.get("/synchronization")
def get_supervision_synchronization():
    try:
        value = project_counter(_read_observer_attribute("supervision_counter_json"))
        return jsonify(schema_version=1, device=TANGO_DEVICE, **value)
    except Exception:
        return jsonify(schema_version=1, owner="supervision", source_host="10.20.30.2",
                       available=False, stale=True, values=None, read_only=True,
                       hardware_acknowledged=False, error="SuperVision counter memory unavailable"), 503


@acq_telemetry_api.get("/owners")
def get_orchestrators():
    try:
        value = _read_observer_attribute("orchestrators_json")
        if (type(value) is not dict or type(value.get("federated")) is not bool
                or type(value.get("owners")) is not dict
                or set(value["owners"]) - {"acquisition", "supervision"}):
            raise ValueError("Unexpected owner metadata")
        def read_only(item):
            if isinstance(item, dict):
                return {key: read_only(nested) for key, nested in item.items() if key != "lease"}
            if isinstance(item, list):
                return [read_only(nested) for nested in item]
            return item
        return jsonify(schema_version=1, device=TANGO_DEVICE, **read_only(value))
    except Exception:
        return jsonify(schema_version=1, owners={}, error="Owner metadata unavailable"), 503


@acq_telemetry_api.get("/video")
def get_raw_video():
    try:
        if set(request.args) - {'channel'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            return jsonify(error='Only one camera channel may be selected'), 400
        try:
            channel = _camera_channel(request.args.get('channel'))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        broker = current_app.extensions.get('supervision_camera_broker')
        value = (broker.snapshot(channel) if broker else read_camera_source(channel)
                 if channel is not None else _present_video(_read_observer_attribute('video_json')))
        return jsonify(value)
    except Exception:
        return jsonify(schema_version=1, owner="supervision", frame=None,
                       available=False, error="Video source unavailable"), 503


@acq_telemetry_api.get('/video/channels')
def get_video_channels():
    try:
        broker = current_app.extensions.get('supervision_camera_broker')
        return jsonify(broker.channels() if broker else read_camera_channels())
    except Exception:
        return jsonify(schema_version=1, owner='supervision', channel_ids=[], channels={},
                       error='Camera channel metadata unavailable'), 503


@acq_telemetry_api.get('/video/stream')
def get_video_stream():
    try:
        if set(request.args) - {'channel', 'fps'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            raise ValueError('Only channel and fps may be selected')
        channel = _camera_channel(request.args.get('channel'))
        fps = float(request.args.get('fps', '25'))
        if fps not in (25., 12.5):
            raise ValueError('Camera display rate must be 25 or 12.5 Hz')
    except ValueError as error:
        return jsonify(error=str(error)), 400
    broker = current_app.extensions.get('supervision_camera_broker')
    if broker is None:
        return jsonify(error='Camera streaming is not configured'), 503
    reservation = None
    release = lambda: None
    if hasattr(broker, 'subscribe'):
        try:
            reservation = broker.subscribe(channel)
            reservation.__enter__()
        except ValueError as error:
            return jsonify(error=str(error)), 429
        released = False
        def release():
            nonlocal released
            if not released:
                released = True
                reservation.__exit__(None, None, None)
    raw_events = broker.events(channel, fps=fps, reserved=True) if reservation else broker.events(channel, fps=fps)
    def scoped_events():
        try:
            yield from raw_events
        finally:
            close = getattr(raw_events, 'close', None)
            if close:
                close()
            release()
    events = scoped_events()
    headers = {'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'}
    # Browsers negotiate and decode gzip themselves. Flush every SSE event so
    # compression never turns into another one-second batching delay.
    if request.accept_encodings.quality('gzip') > 0:
        events = gzip_events(events)
        headers.update({'Content-Encoding': 'gzip', 'Vary': 'Accept-Encoding'})
    response = Response(events, mimetype='text/event-stream', headers=headers)
    response.call_on_close(release)
    return response


@acq_telemetry_api.get("")
def get_telemetry():
    try:
        proxy = tango_gateway.create_device_proxy(DEVICE)
        proxy.set_timeout_millis(1500)
        state, attribute = proxy.read_attributes(["State", "telemetry_json"])
        if state.has_failed or attribute.has_failed:
            raise ValueError("Tango telemetry attribute unavailable")
        return jsonify(present_snapshot(attribute.value, str(state.value)))
    except Exception as error:
        # No fallback to PSP, card reads or another Tango device.
        current_app.logger.warning(
            "ACQ telemetry read unavailable: %s", type(error).__name__
        )
        return jsonify(
            schema_version=1,
            execution_allowed=False,
            hardware_writes=False,
            quality="UNAVAILABLE",
            error="Récepteur de télémétrie Tango indisponible.",
        ), 503


@acq_telemetry_api.get("/archive")
def get_archive_status():
    try:
        proxy = tango_gateway.create_device_proxy(DEVICE)
        proxy.set_timeout_millis(2000)
        attr = proxy.read_attribute('archive_status_json')
        if attr.has_failed:
            raise ValueError('Archive status unavailable')
        value = json.loads(attr.value)
        if request.args.get('include_imports') == '1':
            try:
                reader = local_history_store()
                summary = reader.summary() if reader else json.loads(proxy.command_inout('ArchiveSummary'))
                value['imports'] = summary['imports']
                value['frames'] = summary['frames']
            except Exception:
                value['imports_status'] = 'UNKNOWN'
        return jsonify(value)
    except Exception:
        return jsonify(available=False, error='Archive status unavailable'), 503


@acq_telemetry_api.get('/history-view')
def get_history_view():
    return Response(Path(__file__).with_name('telemetry_history.html').read_text(encoding='utf-8'),
                    mimetype='text/html')


@acq_telemetry_api.get("/history")
def get_history():
    allowed = {'bank', 'index', 'start', 'end', 'limit', 'cursor_time', 'cursor_uid'}
    try:
        if set(request.args) - allowed or any(len(request.args.getlist(k)) != 1 for k in request.args):
            raise ValueError('Invalid history query')
        query = dict(request.args)
        query['index'] = int(query['index'])
        query['limit'] = int(query.get('limit', 1000))
        if query.get('bank') not in BANKS or not 0 <= query['index'] <= 8191 or not 1 <= query['limit'] <= 5000:
            raise ValueError('Invalid history channel or limit')
        for key in ('start', 'end'):
            parsed = datetime.fromisoformat(query[key].replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                raise ValueError('History timestamps require timezone')
    except (ValueError, KeyError):
        return jsonify(error='Known bank, index, timezone-qualified start/end and limit 1..5000 required'), 400
    try:
        reader = local_history_store()
        if reader is not None:
            return jsonify(browser_data(reader.read_history(query)))
        proxy = tango_gateway.create_device_proxy(DEVICE)
        proxy.set_timeout_millis(4000)
        raw = proxy.command_inout('ReadHistory', json.dumps(query))
        return jsonify(browser_data(json.loads(raw)))
    except Exception as error:
        current_app.logger.warning('ACQ PostgreSQL history unavailable: %s', type(error).__name__, exc_info=True)
        return jsonify(error='PostgreSQL history unavailable; live telemetry is separate'), 503


@acq_telemetry_api.get("/cooling")
def get_cooling_safety():
    """Observe the selected producer through the one telemetry/control DS.

    Legacy labview/xp_control labels are configuration aliases, not alternate
    transports. The retired xp_runtime DS is never contacted or substituted.
    """
    source = current_app.config.get("ELYSE_COOLING_SOURCE", "unified")
    try:
        if source not in ("unified", "labview", "xp_control"):
            raise ValueError("Retired or unknown cooling source; select unified telemetry DS")
        proxy = tango_gateway.create_device_proxy(DEVICE)
        proxy.set_timeout_millis(1500)
        state, attr = proxy.read_attributes(["State", "telemetry_json"])
        if state.has_failed or attr.has_failed or str(state.value) != "ON":
            raise ValueError("Telemetry receiver not ready")
        body = present_snapshot(attr.value, str(state.value))
        safety = body["cooling_safety"]
        source = "xp_control" if body["source"] == "python_daqmx_acquisition" else "labview"
        if not isinstance(safety, dict) or safety.get("schema_version") != 1:
            raise ValueError("Cooling alarm service not installed on selected source")
        if source == "labview" and safety.get("automatic_stop_available") is not False:
            raise ValueError("Read-only LabVIEW receiver cannot claim shutdown authority")
        if (safety.get("timeout_seconds") != 120 or type(safety.get("active")) is not bool
                or type(safety.get("automatic_stop_available")) is not bool
                or safety.get("stop_state") not in ("NONE", "REQUESTED", "UNAVAILABLE", "INTERRUPTED", "FAILED", "COMPLETED")
                or not isinstance(safety.get("circuits"), list)
                or len(safety["circuits"]) > 2):
            raise ValueError("Invalid cooling alarm schema")
        seen = set()
        for incident in safety["circuits"]:
            if not isinstance(incident, dict) or incident.get("circuit") not in ("CANON", "SECTION"):
                raise ValueError("Invalid cooling circuit")
            if incident["circuit"] in seen:
                raise ValueError("Duplicate cooling incident")
            seen.add(incident["circuit"])
            for key in ("started_utc", "deadline_utc"):
                if datetime.fromisoformat(incident[key]).utcoffset() is None:
                    raise ValueError("Timezone required for cooling alarm")
            remaining = incident.get("remaining_seconds")
            if type(remaining) not in (int, float) or not math.isfinite(remaining) or not 0 <= remaining <= 120:
                raise ValueError("Invalid cooling countdown")
        if safety["active"] != bool(safety["circuits"]):
            raise ValueError("Inconsistent cooling alarm state")
        # Preserve the existing operator journal without changing which one
        # telemetry DS owns this read. Journal errors remain separately visible.
        archive_error = ''
        try:
            from supervision_workspace_api import store
            journal_store = store()
            journal_store.record_journal(journal_store.journal.observe_cooling, source, safety)
            archive_error = journal_store.journal_error
        except Exception as error:
            archive_error = 'Journal SQLite indisponible: ' + str(error)[:250]
        # This route is observation-only even when XP independently owns a
        # locally commissioned stop policy. It never submits that stop.
        return jsonify(schema_version=1, execution_allowed=False, hardware_writes=False,
                       source=source, topology=topology(), cooling_safety=safety, archive_error=archive_error)
    except Exception as error:
        current_app.logger.warning("Cooling alarm source unavailable: %s", type(error).__name__)
        archive_error = ''
        try:
            from supervision_workspace_api import store
            journal_store = store()
            journal_store.record_journal(journal_store.journal.cooling_unavailable, source, str(error)[:300])
            archive_error = journal_store.journal_error
        except Exception as storage_error:
            archive_error = 'Journal SQLite indisponible: ' + str(storage_error)[:250]
        return jsonify(schema_version=1, execution_allowed=False, hardware_writes=False,
                       source=source, error="Service d’alarme refroidissement indisponible.", archive_error=archive_error), 503
