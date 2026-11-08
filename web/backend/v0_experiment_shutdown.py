"""Bounded V0 shutdown: park its delay stage, warm Andor, then remove power."""

import json
import math
import time

from pump_probe_v0_config import STAGE_MIN_MM, STAGE_MAX_MM

SD1 = "manip/SD1/PDU_SD1"
SD2 = "manip/SD2/PDU_SD2"
STREAK = "manip/camera/hamamatsu_streak_main"
CAMERA = "manip/CR/ANDOR_CCD1"
STAGE = "manip/general/DS_OWIS_Aggregator"
STAGE_BACKEND = "manip/general/DS_OWIS_PS90_IP"
STAGE_AXIS = 3  # Laser Pointing 2 TranslationStage1; not sample or VD2 axes.
STAGE_POWER = "manip/V0/PDU_VO"
STAGE_TOLERANCE_MM = 0.01
STAGE_TIMEOUT_S = 900.0  # Includes a 700 mm return at the configured 1 mm/s.
# Hardware topology verified from registry/PDU output names on 2026-10-14.
OUTPUT_PLAN = ((SD2, 2, "DG645"), (SD1, 1, "Andor / UV-vis"),
               (SD2, 4, "Power_current"), (SD2, 3, "Power_control"))
WARMUP_TIMEOUT_S = 900.0


class ShutdownFailure(RuntimeError):
    def __init__(self, message, steps):
        super().__init__(message)
        self.steps = steps


def phase(steps, message, stage=0):
    publish = getattr(steps, "phase", None)
    if publish:
        publish(message, stage=stage)


def power_snapshot(proxy):
    ids = list(map(int, proxy.read_attribute("ids").value))
    states = list(map(int, proxy.read_attribute("states").value))
    if len(ids) != len(states) or not ids or len(set(ids)) != len(ids) or any(s not in (0, 1) for s in states):
        raise RuntimeError("PDU output ID/state readback invalid; no power changes attempted")
    return ids, states


def switch_off(proxy, output, label, steps):
    ids, before = power_snapshot(proxy)
    if output not in ids:
        raise RuntimeError(f"Required PDU output {output} is missing")
    desired = before.copy()
    desired[ids.index(output)] = 0
    if desired != before:
        proxy.command_inout("set_channels_states", desired)  # once; never replay timeout
    deadline = time.monotonic() + 8.0
    while True:
        observed_ids, observed = power_snapshot(proxy)
        readback = dict(zip(observed_ids, observed))
        if set(observed_ids) != set(ids) or any(readback.get(i) != before[n] for n, i in enumerate(ids) if i != output):
            raise RuntimeError(f"Unrelated outlets changed while switching off {label}; outcome unverified")
        if readback[output] == 0:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Power OFF not confirmed: {label}")
        time.sleep(0.5)
    steps.append({"step": label, "status": "verified OFF" if desired != before else "already OFF; unchanged"})


def _safety_reply(value):
    data = json.loads(str(value))
    if data.get("fresh_sdk_readback") is not True:
        raise RuntimeError("Andor shutdown requires fresh native SDK readback")
    temperature = data.get("temperature_c")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not math.isfinite(temperature):
        raise RuntimeError("Andor shutdown temperature unverified")
    if not isinstance(data.get("cooler_on"), bool) or not isinstance(data.get("acquisition_active"), bool):
        raise RuntimeError("Andor cooler/acquisition readback unverified")
    return data


def _stage_readback(backend):
    # Commands request native controller reads, not polled aggregator attributes.
    state = str(backend.command_inout("get_status_axis", STAGE_AXIS)).upper().rsplit(".", 1)[-1]
    state = {"0": "ON", "7": "STANDBY", "6": "MOVING", "10": "RUNNING"}.get(state, state)
    if state not in {"ON", "STANDBY", "MOVING", "RUNNING"}:
        raise RuntimeError(f"V0 translation stage axis 3 is not available: {state}")
    raw = backend.command_inout("read_position_axis", STAGE_AXIS)
    if isinstance(raw, bool):
        raise RuntimeError("V0 translation stage position is invalid")
    position = float(raw)
    # Legacy OWIS adapters can return their last position after a failed read.
    # Do not mistake that cached number for a successful return to zero.
    error = str(backend.read_attribute("last_error").value).strip()
    if not math.isfinite(position) or error:
        raise RuntimeError(f"V0 translation stage readback unverified: {error or 'non-finite position'}")
    return position, state


def park_translation_stage(proxy_factory, steps):
    """One absolute move to physical 0 mm; never home or redefine coordinates."""
    locks = []
    stage = None
    move_issued = False
    try:
        # Reserve the routing entry point and prevent a new laser-pointing move.
        # Do not lock the backend: aggregator commands originate in its server.
        for name in ("manip/V0/LaserPointing-Cam1", "manip/V0/LaserPointing-Cam2", STAGE):
            device = proxy_factory(name)
            device.set_timeout_millis(5000)
            device.lock(int(STAGE_TIMEOUT_S + 60))
            locks.append(device)
            if name == STAGE:
                stage = device
                continue
            status = str(device.read_attribute("automatic_search_status").value)
            progress = json.loads(str(device.read_attribute("automatic_search_progress").value))
            if status in {"running", "paused"} or progress.get("phase") in {"manual_point", "applying_point", "restoring"}:
                raise RuntimeError(f"{name} is active; no competing translation-stage move issued")
            if json.loads(str(device.read_attribute("alignment_pending_reference_json").value)):
                raise RuntimeError(f"{name} has a pending alignment decision; stage not moved")
        pdu = proxy_factory(STAGE_POWER)
        pdu.set_timeout_millis(5000)
        ids, states = power_snapshot(pdu)
        if dict(zip(ids, states)).get(2) != 1:
            raise RuntimeError("OWIS power V0/2 is OFF or unknown; Unprepare does not switch it on")
        backend = proxy_factory(STAGE_BACKEND)
        backend.set_timeout_millis(5000)
        initial, state = _stage_readback(backend)
        if state in {"MOVING", "RUNNING"}:
            raise RuntimeError("V0 translation stage already moving; foreign motion not interrupted")
        if not STAGE_MIN_MM <= initial <= STAGE_MAX_MM:
            raise RuntimeError(f"V0 translation stage initial position {initial:g} mm is outside the approved travel range")
        phase(steps, f"Returning V0 translation stage axis 3 from {initial:.3f} mm to 0 mm", stage=0)
        deadline = time.monotonic() + STAGE_TIMEOUT_S
        if abs(initial) > STAGE_TOLERANCE_MM:
            move_issued = True  # A command timeout can still mean movement started.
            reply = stage.command_inout("move_axis", [float(STAGE_AXIS), 0.0])
            if reply not in (0, "0"):
                raise RuntimeError(f"V0 translation-stage return was not accepted: {reply}")
        stable = 0
        next_progress = 0.0
        while True:
            position, state = _stage_readback(backend)
            stable = stable + 1 if abs(position) <= STAGE_TOLERANCE_MM and state in {"ON", "STANDBY"} else 0
            if stable >= 3:
                break
            now = time.monotonic()
            if now >= deadline:
                raise TimeoutError(f"V0 translation stage did not reach 0 mm within {STAGE_TIMEOUT_S:g} s; actual {position:.3f} mm")
            if now >= next_progress:
                phase(steps, f"V0 translation stage axis 3: {position:.3f} mm; waiting for verified 0 mm", stage=0)
                next_progress = now + 5.0
            time.sleep(0.5)
        steps.append({"step": "V0 translation stage", "status": "verified 0 mm (3 stationary readbacks)",
                      "device": STAGE, "axis": STAGE_AXIS, "initial_mm": initial,
                      "final_mm": position, "tolerance_mm": STAGE_TOLERANCE_MM})
    except Exception as exc:
        if move_issued:
            try:
                reply = stage.command_inout("stop_axis", STAGE_AXIS)
                if reply not in (0, "0"):
                    raise RuntimeError(str(reply))
            except Exception as stop_error:
                raise RuntimeError(f"{exc}; stage stop unverified: {stop_error}; OWIS power retained") from exc
        raise
    finally:
        unlock_errors = []
        for device in reversed(locks):
            try:
                device.unlock()
            except Exception as exc:
                unlock_errors.append(str(exc))
        if unlock_errors:
            raise RuntimeError("V0 stage ownership-lock release unverified: " + "; ".join(unlock_errors))


def _camera_commands(proxy, steps):
    # Reconnection is read-only. Never restart/open a cold camera in Unprepare.
    for attempt in range(1, 4):
        try:
            return set(proxy.get_command_list())
        except Exception as exc:
            phase(steps, f"Andor server connection unavailable ({attempt}/3); camera power retained", stage=1)
            if attempt == 3:
                raise RuntimeError("Andor server unavailable after 3 read-only connection attempts; "
                                   "restore its connection on Elysium2 before retrying safe shutdown. "
                                   f"CCD temperature is unknown; power retained. {exc}") from exc
            time.sleep(1.1)  # Longer than Tango's reconnect backoff; no write replay.


def release_camera(proxy, steps):
    proxy.set_timeout_millis(5000)
    required = {"BeginSafePowerOff", "GetPowerOffSafety", "ReleaseAfterWarmup"}
    if not required.issubset(_camera_commands(proxy, steps)):
        raise RuntimeError("Andor server lacks verified warm-up commands; retain camera power and update its server safely")
    locked = False
    try:
        proxy.lock(30)
        locked = True
        phase(steps, "Stopping Andor acquisition and disabling cooler; fan/camera power retained", stage=1)
        safety = _safety_reply(proxy.command_inout("BeginSafePowerOff"))
        deadline = time.monotonic() + WARMUP_TIMEOUT_S
        while True:
            if safety["cooler_on"] or safety["acquisition_active"]:
                raise RuntimeError("Andor cooler or acquisition remains active; camera power retained")
            phase(steps, f"Andor CCD warm-up: {safety['temperature_c']:.1f} C; waiting for >= 0 C, power retained", stage=1)
            if safety["temperature_c"] >= 0.0:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Andor warm-up exceeded 15 minutes; camera power retained, recheck manually")
            time.sleep(2.0)
            safety = _safety_reply(proxy.command_inout("GetPowerOffSafety"))
        proxy.command_inout("ReleaseAfterWarmup")
        if str(proxy.state()).rsplit(".", 1)[-1].upper() != "OFF":
            raise RuntimeError("Andor SDK release not verified; camera power retained")
        steps.append({"step": "Andor warm-up / SDK", "status": "verified warm, cooler OFF, acquisition stopped, SDK released"})
    finally:
        if locked:
            proxy.unlock()


def execute_shutdown(proxy_factory, steps, stop_web_acquisition, vd2_status):
    errors = []
    pdus = {}
    def verify_shared_idle(sd2):
        ids, states = power_snapshot(sd2)
        if dict(zip(ids, states)).get(1) != 0:
            raise RuntimeError("VD2 streak-camera output SD2/1 is ON or unknown; shared V0/VD2 power retained")
        status = vd2_status()
        if status["application_running"] or status["connected"] or status["protocol_active"] or status["lifecycle_active"]:
            raise RuntimeError("VD2 software/measurement is active; shared V0/VD2 power retained")
    phase(steps, "Checking shared VD2 supplies before V0 shutdown", stage=0)
    try:
        sd2 = proxy_factory(SD2)
        sd2.set_timeout_millis(5000)
        verify_shared_idle(sd2)
        pdus[SD2] = sd2
    except Exception as exc:
        # This is a global ownership guard, not a recoverable hardware branch.
        raise ShutdownFailure(str(exc), steps) from exc

    stop_web_acquisition()
    steps.append({"step": "V0 acquisition", "status": "web sequence stopped; pending data finalized"})
    try:
        verify_shared_idle(pdus[SD2])
        switch_off(pdus[SD2], 2, "SD2/2 DG645", steps)
    except Exception as exc:
        errors.append(f"DG645 power-off unverified: {exc}")
        steps.append({"step": "DG645", "status": "failed", "detail": str(exc)})
        # Trigger power-off is a prerequisite to removing camera/bias supplies.
        raise ShutdownFailure("; ".join(errors), steps) from exc

    parked = False
    try:
        verify_shared_idle(pdus[SD2])
        park_translation_stage(proxy_factory, steps)
        parked = True
    except Exception as exc:
        errors.append(f"V0 translation stage not parked: {exc}; OWIS power retained")
        steps.append({"step": "V0 translation stage", "status": "failed", "detail": str(exc)})

    try:
        sd1 = proxy_factory(SD1)
        sd1.set_timeout_millis(5000)
        pdus[SD1] = sd1
        ids, states = power_snapshot(sd1)
        powered = dict(zip(ids, states)).get(1)
        if powered is None:
            raise RuntimeError("Andor supply SD1/1 is missing")
        if powered:
            release_camera(proxy_factory(CAMERA), steps)
            switch_off(sd1, 1, "SD1/1 Andor / UV-vis", steps)
        else:
            steps.append({"step": "SD1/1 Andor / UV-vis", "status": "already OFF; no camera discovery or restart"})
    except Exception as exc:
        errors.append(f"Andor power retained: {exc}")
        steps.append({"step": "Andor", "status": "failed", "detail": str(exc)})
    phase(steps, "Disabling only Power_current and Power_control; unrelated supplies retained", stage=2)
    for output, label in ((4, "SD2/4 Power_current"), (3, "SD2/3 Power_control")):
        try:
            # Warm-up can take minutes. Recheck ownership, not an old snapshot.
            verify_shared_idle(pdus[SD2])
            switch_off(pdus[SD2], output, label, steps)
        except Exception as exc:
            errors.append(f"{label} power-off unverified: {exc}")
            steps.append({"step": label, "status": "failed", "detail": str(exc)})
    steps.append({"step": "Retained equipment", "status": "STANDA/Elysium2, shared OWIS power, other OWIS axes, VD2 outlets and Xe lamp cooling unchanged; Tango servers retained"})
    for device in dict.fromkeys(item[0] for item in OUTPUT_PLAN):
        if device not in pdus:
            continue
        try:
            ids, states = power_snapshot(pdus[device])
            observed = dict(zip(ids, states))
            remaining = [label for planned, output, label in OUTPUT_PLAN if planned == device and observed.get(output) != 0]
            if remaining:
                errors.append("Final power-off readback unverified: " + ", ".join(remaining))
        except Exception as exc:
            errors.append(f"Final power-off readback unavailable for {device}: {exc}")
    if parked:
        try:
            position, state = _stage_readback(proxy_factory(STAGE_BACKEND))
            if abs(position) > STAGE_TOLERANCE_MM or state not in {"ON", "STANDBY"}:
                raise RuntimeError(f"actual {position:.3f} mm, state {state}")
        except Exception as exc:
            errors.append(f"Final V0 translation-stage zero unverified: {exc}")
            steps.append({"step": "V0 translation stage final readback", "status": "failed", "detail": str(exc)})
    if errors:
        raise ShutdownFailure("; ".join(errors), steps)
    return {"steps": steps, "warnings": [], "message": "V0 translation stage axis 3 verified at 0 mm. V0 supplies verified OFF: Andor SD1/1, DG645 SD2/2, Power_current SD2/4, Power_control SD2/3. Other axes, shared OWIS power and Xe cooling unchanged; Tango servers retained."}
