"""Prepare the V0 detector and verify its external or internal DG645 clock."""

import copy
import hashlib
import json
from pathlib import Path
import time


def prepare_acquisition(api, progress=None):
    controller = api._emulator
    config = controller.hardware_config()
    folder = Path.home() / ".pyconlyse" / "v0-timing"
    checks = []

    def record(check):
        checks.append(check)
        if progress is not None:
            progress.append({**check, "step": check["label"],
                             "status": "verified" if check.get("ok") else "failed"})
        return check.get("ok")

    def phase(message):
        if progress is not None:
            progress.phase(message, stage=2)

    phase("Confirming V0 CCD power and detector servers")
    output = next(item for item in api.REQUIRED_NETIO_OUTPUTS if item["key"] == "uv_vis")
    power_ok = record(controller._check_netio_output(output, fix=True))
    camera_ok = False
    for label, name in [("Andor CCD", config["andor_device"]),
                        ("Andor Shamrock", config["spectrograph_device"])]:
        phase(f"Checking {label}")
        check = (controller._check_device(label, name, fix=True, starter_name=api.V0_STARTER_DEVICE)
                 if power_ok else api._json_fail(label, "CCD/UV-vis power is unverified", blocked=True))
        if label == "Andor CCD":
            camera_ok = check.get("ok")
        record(check)

    if not camera_ok:
        record(api._json_fail("V0 synchronization", "Andor CCD is unavailable; clock was not changed"))
        return checks

    generator = None
    clock_claimed = False
    camera = None
    camera_started = False
    try:
        camera = api._tango_proxy(config["andor_device"], timeout_ms=15000)
        caps = json.loads(camera.command_inout("V0Capabilities"))
        if (caps.get("configuration_fresh") is not True or caps.get("external_trigger") is not True
                or caps.get("track_count") != 2 or caps.get("read_mode") != "multi_track"):
            raise RuntimeError("Configure Andor for external trigger and two-track readout before preparing V0")
        if caps.get("acquisition_active"):
            if getattr(controller, "_prepared_camera_epoch", None) is None:
                try:
                    marker = json.loads((folder / "prepared.json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    marker = {}
                if (marker.get("camera") == config["andor_device"]
                        and marker.get("generator") == config["dg645_device"]
                        and marker.get("epoch") == caps.get("acquisition_epoch")
                        and marker.get("camera_fingerprint") == caps.get("config_fingerprint")):
                    timing_path = Path(marker["timing_path"])
                    if timing_path.parent.resolve() != folder.resolve():
                        raise RuntimeError("Saved V0 timing path is invalid")
                    config.update(dg645_recall_config=str(timing_path), dg645_preflight_policy="verify_only")
                    controller._prepared_camera_epoch = marker["epoch"]
            if (getattr(controller, "_prepared_camera_epoch", None) != caps.get("acquisition_epoch")
                    or config.get("dg645_preflight_policy") != "verify_only"):
                raise RuntimeError("Andor acquisition is already active; clock was not changed")
            generator = api._tango_proxy(config["dg645_device"], timeout_ms=8000)
            saved = api._load_dg645_recall_config(config["dg645_recall_config"])
            for query, expected in saved["snapshot"]["raw_queries"].items():
                if query != "*IDN?" and not api._values_match(
                        expected, str(generator.command_inout("scpi_query", query)).strip()):
                    raise RuntimeError(f"Prepared V0 clock changed: {query}")
            source = int(float(generator.command_inout("scpi_query", "TSRC?")))
            with controller._lock:
                controller._hardware_config.update(control_mode="tango",
                    dg645_recall_config=config["dg645_recall_config"], dg645_preflight_policy="verify_only")
            record(api._json_ok("V0 synchronization", "Andor remains armed; prepared DG645 timing verified",
                                trigger_source=source, external_pulses=source == 1,
                                internal_rate_hz=5 if source == 0 else None))
            return checks
        phase("Verifying V0 recall 8 with DG645 in standby")
        recall = api._load_dg645_recall_config(api.DEFAULT_DG645_RECALL_CONFIG)
        generator = api._tango_proxy(config["dg645_device"], timeout_ms=8000)
        if str(generator.state()).split(".")[-1] != "ON":
            raise RuntimeError("DG645 is not ON")
        generator.command_inout("scpi_write", f"*RCL {int(recall['recall_slot'])}")
        clock_claimed = True
        generator.command_inout("scpi_write", "TSRC 5")
        time.sleep(1)
        if float(generator.command_inout("scpi_query", "TSRC?")) != 5:
            raise RuntimeError("DG645 standby readback failed")
        queries = recall["snapshot"]["raw_queries"]
        for query, expected in queries.items():
            if query in {"*IDN?", "TSRC?", "TRAT?"}:
                continue
            actual = str(generator.command_inout("scpi_query", query)).strip()
            if not api._values_match(expected, actual):
                raise RuntimeError(f"V0 DG645 timing mismatch for {query}: {actual}")
        phase("Arming Andor external-trigger readout")
        camera_started = True
        camera.command_inout("start_grabbing")
        armed = json.loads(camera.command_inout("V0Capabilities"))
        if armed.get("acquisition_active") is not True or armed.get("external_trigger") is not True:
            raise RuntimeError("Andor did not confirm external-trigger acquisition: "
                               + str(armed.get("admission_error") or "readback is incomplete"))
        phase("Checking ELYSE synchronization pulses")
        first = controller._read_daq_counter()
        time.sleep(1.25)
        second = controller._read_daq_counter()
        external = second > first
        if external:
            source = 1
            rate = float(generator.command_inout("scpi_query", "TRAT?"))
        else:
            source, rate = 0, 5.0
            generator.command_inout("scpi_write", "TRAT 5")
            if float(generator.command_inout("scpi_query", "TRAT?")) != 5:
                raise RuntimeError("DG645 internal 5 Hz readback failed")
        generator.command_inout("scpi_write", f"TSRC {source}")
        if float(generator.command_inout("scpi_query", "TSRC?")) != source:
            raise RuntimeError("DG645 did not confirm the selected trigger source")

        timing = copy.deepcopy(recall)
        timing["snapshot"]["raw_queries"].update({"TSRC?": str(source), "TRAT?": str(rate)})
        encoded = json.dumps(timing, sort_keys=True, indent=2)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        folder.mkdir(parents=True, exist_ok=True)
        timing_path = folder / f"{digest}.json"
        timing_path.write_text(encoded, encoding="utf-8")
        marker = {"camera": config["andor_device"], "generator": config["dg645_device"],
                  "epoch": armed.get("acquisition_epoch"), "camera_fingerprint": armed.get("config_fingerprint"),
                  "timing_path": str(timing_path)}
        marker_pending = folder / "prepared.pending.json"
        marker_pending.write_text(json.dumps(marker), encoding="utf-8")
        marker_pending.replace(folder / "prepared.json")
        with controller._lock:
            controller._hardware_config.update(control_mode="tango", dg645_recall_config=str(timing_path),
                                               dg645_preflight_policy="verify_only")
            controller._prepared_camera_epoch = armed.get("acquisition_epoch")
        mode = "External ELYSE" if external else "Internal 5 Hz"
        record(api._json_ok("V0 synchronization", f"{mode}; ELYSE counter {first} → {second}; Andor armed",
                            trigger_source=source, external_pulses=external, internal_rate_hz=5 if not external else None,
                            counter_before=first, counter_after=second, timing_path=str(timing_path)))
    except Exception as exc:
        cleanup = ""
        if generator is not None and clock_claimed:
            try:
                generator.command_inout("scpi_write", "TSRC 5")
                if float(generator.command_inout("scpi_query", "TSRC?")) != 5:
                    raise RuntimeError("DG645 standby is unverified")
            except Exception as error:
                cleanup = f"; cleanup: {error}"
        if camera_started:
            try:
                camera.command_inout("stop_grabbing")
            except Exception as error:
                cleanup += f"; Andor stop unverified: {error}"
        record(api._json_fail("V0 synchronization", f"{exc}{cleanup}"))
    return checks
