"""HTTP integration for the managed VD2 paired measurement."""
from dataclasses import asdict

from flask import jsonify

from vd2_measurement_protocol import Vd2ProtocolError
from vd2_paired_acquisition import PairedRequest, TRIGGER_SOURCES, target_error


START_FIELDS = {
    "output_root", "sample_name", "reuse_bruit", "mode", "first_map_with_electrons",
    "pair_limit", "target_mod", "trigger_source", "roi", "band", "method", "sam_surface_percent",
}


def install_paired_routes(api):
    blueprint = api.pump_probe_vd2_api

    @blueprint.post("/paired/start")
    @api._serialized_vd2_mutation
    def paired_start():
        from treatment_api import _ensure_within_allowed_root

        payload, blocked = api._mutation_payload(START_FIELDS)
        if blocked is not None:
            return blocked
        if not api.VD2_CAMERA_ONLY:
            return jsonify(success=False, error="Paired acquisition requires camera-only HPD-TA"), 409
        try:
            plan = PairedRequest.from_payload(payload, _ensure_within_allowed_root)
            timing = {"warmup_seconds": 10, "base_rate_hz": 5,
                      "burst_period_s": 0.1, "burst_count": 2,
                      "trigger_source": TRIGGER_SOURCES[plan.trigger_source], "stop_burst": 0}
            commands = ("StartSequence", "SaveCurrentSequence", "StopSequence", "write_attribute:sequence_loops"
                        ) if plan.native_sequence else ("StartPairedLive", "StopPairedLive")
            blocked = api._approval_or_response(
                "paired.start",
                [api._target(api.DG645_DEVICE, "scpi_write"),
                 *(api._target(api.STREAK_DEVICE, cmd) for cmd in commands)],
                {**asdict(plan), "timing": timing}, "vd2.paired.start", START_FIELDS,
            )
            if blocked is not None:
                return blocked
            if api._protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
                raise ValueError("Another VD2 acquisition owns the camera")
            state = api._paired_acquisition.start(api, plan)
            return jsonify(success=True, paired=state), 202
        except (KeyError, TypeError, ValueError, OSError, Vd2ProtocolError) as exc:
            return jsonify(success=False, error=str(exc)), 409

    def control_paired(action):
        fields = {"job_id"} if action == "stop" else {"job_id", "target_mod"}
        payload, blocked = api._mutation_payload(fields)
        if blocked is not None:
            return blocked
        try:
            job = payload["job_id"]
            if type(job) is not str or len(job) != 32 or api._paired_acquisition.status().get("job_id") != job:
                raise ValueError("Paired measurement is no longer active")
            target = target_error(payload["target_mod"]) if action == "target" else None
            blocked = api._approval_or_response(
                f"paired.{action}",
                [api._target(api.DG645_DEVICE, "scpi_write"), api._target(
                    api.STREAK_DEVICE, "StopSequence" if api._paired_acquisition.status().get("capture") == "sequence"
                    else "StopPairedLive")],
                {"job_id": job, **({"target_mod": target} if action == "target" else {})},
                f"vd2.paired.{action}", fields,
            )
            if blocked is not None:
                return blocked
            state = (api._paired_acquisition.stop(job) if action == "stop"
                     else api._paired_acquisition.set_target(job, target))
            return jsonify(success=True, paired=state)
        except (KeyError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 409

    @blueprint.post("/paired/stop")
    def paired_stop():
        return control_paired("stop")

    @blueprint.post("/paired/target")
    def paired_target():
        return control_paired("target")
