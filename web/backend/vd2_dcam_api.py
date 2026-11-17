"""Opt-in VD2 dark readout through the Hamamatsu DCAM driver."""

from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import uuid4

from flask import jsonify, request
import numpy as np
import psutil

from DeviceServers.cameras.hamamatsu_streak.dcam_readout_probe import (
    EXPOSURE_S, capture_blank, open_readout, require_exclusive_readout, save_blank,
)


OWNER_KEY = "vd2_dcam_owner"
INTENT = {"readout": "dcam"}


class DcamReadout:
    """Use one thread per SDK handle, including start, stop and close."""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vd2-dcam")
        self.lock = Lock()
        self.pending = None
        self.camera = None
        self.device = None
        self.live = False
        self.original = None
        self.preview = None
        self.frame_stamp = None
        self.next_preview = 0.0

    def call(self, fn, *args):
        with self.lock:
            if self.pending is not None and not self.pending.done():
                raise RuntimeError("A DCAM operation is still in progress")
            self.pending = self.executor.submit(fn, *args)
            work = self.pending
        try:
            return work.result(timeout=20)
        except TimeoutError as exc:
            raise RuntimeError("DCAM did not respond within 20 s; acquisition state must be rechecked") from exc

    def open(self):
        if self.camera is None:
            self.camera, self.device = open_readout()

    def start(self):
        require_exclusive_readout()
        if self.live:
            return
        self.original = self.camera.get_trigger_mode(), self.camera.get_exposure()
        try:
            if self.camera.set_trigger_mode("int") != "int":
                raise RuntimeError("DCAM internal sensor trigger did not verify")
            self.camera.set_exposure(EXPOSURE_S)
            self.camera.start_acquisition(mode="sequence", nframes=8)
        except Exception:
            self.stop()
            raise
        self.preview = self.frame_stamp = None
        self.next_preview = 0.0
        self.live = True

    def stop(self):
        if self.original is None:
            return
        self.camera.stop_acquisition()
        trigger, exposure = self.original
        self.camera.set_exposure(exposure)
        self.camera.set_trigger_mode(trigger)
        self.live = False
        self.original = None
        self.preview = None

    def close(self):
        if self.camera is not None:
            self.stop()
            self.camera.close()
            self.camera = self.device = None
        self.preview = None

    def read_frame(self):
        require_exclusive_readout()
        if not self.live:
            return None
        now = monotonic()
        if now < self.next_preview:
            return self.preview
        self.next_preview = now + 0.1
        latest = self.camera.read_newest_image(peek=True, return_info=True)
        if latest is None:
            return self.preview
        image, info = latest
        if image is None or info.framestamp == self.frame_stamp:
            return self.preview
        # Preserve 16-bit data in recorded blanks. Only the Web image is scaled.
        image = image[::4, ::4]
        low, high = np.percentile(image, (1, 99))
        scale = 255.0 / max(1, high - low)
        pixels = np.clip((image.astype(np.float32) - low) * scale, 0, 255).astype(np.uint8)
        self.frame_stamp = info.framestamp
        self.preview = {
            "width": pixels.shape[1], "height": pixels.shape[0],
            "pixels_b64": b64encode(pixels.tobytes()).decode("ascii"),
            "frame_stamp": self.frame_stamp, "received_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.preview

    def blank(self, output):
        require_exclusive_readout()
        if self.live or self.original is not None:
            raise RuntimeError("Stop DCAM Live before recording a blank")
        return save_blank(output, *capture_blank(self.camera, self.device))


def install_dcam_routes(api):
    routes = api.pump_probe_vd2_api
    readout = DcamReadout()

    def owner():
        return api._lifecycle().get(OWNER_KEY)

    def this_process():
        process = psutil.Process()
        return {"pid": process.pid, "created_at": process.create_time()}

    def power(device, outlet):
        outputs = api._wait_for_device(device, timeout_s=5.0)
        ids = list(map(int, api._value(outputs, "ids")))
        states = list(map(int, api._value(outputs, "states")))
        if len(ids) != len(states) or len(ids) != len(set(ids)) or outlet not in ids:
            raise RuntimeError(f"Cannot verify outlet {outlet} on {device}")
        state = states[ids.index(outlet)]
        if state not in (0, 1):
            raise RuntimeError(f"Invalid power readback for {device} outlet {outlet}")
        return outputs, state

    def check_dark():
        require_exclusive_readout()
        if power(api.ZABER_PDU_DEVICE, 1)[1] != 0:
            raise RuntimeError("Verify the flashlamp supply is OFF for DCAM dark readout")
        dg = api._wait_for_device(api.DG645_DEVICE, timeout_s=5.0)
        if any(float(dg.command_inout("scpi_query", command)) != expected
               for command, expected in (("TSRC?", 5), ("BURM?", 0))):
            raise RuntimeError("DCAM dark readout requires DG645 internal standby with Burst OFF")

    def prepare(steps):
        check_dark()
        pdu, state = power(api.VD2_PDU_DEVICE, 1)
        if state or owner() is not None:
            raise RuntimeError("Unprepare the existing VD2 setup before preparing DCAM")
        api._lifecycle().put(OWNER_KEY, this_process())
        api._progress(steps, "Powering the camera outlet for DCAM dark readout")
        api._enable_required_power(pdu, steps, {1: "Streak camera / spectrograph"}, "SD2")
        check_dark()
        readout.call(readout.open)
        steps.power_ready()
        steps.append({"step": "DCAM", "status": f"{readout.device.model} ready"})
        return {"message": "DCAM dark readout ready", "steps": list(steps)}

    def shutdown(steps):
        marked = owner()
        if marked is None:
            return {"message": "DCAM is already off", "steps": list(steps)}
        current = this_process()
        if marked != current:
            try:
                old = psutil.Process(marked["pid"])
                if old.create_time() == marked["created_at"]:
                    raise RuntimeError("Another Web process still owns the DCAM camera")
            except psutil.NoSuchProcess:
                pass
        require_exclusive_readout()
        api._progress(steps, "Stopping DCAM and releasing the camera SDK")
        readout.call(readout.close)
        pdu, _ = power(api.VD2_PDU_DEVICE, 1)
        api._disable_pdu_outputs(pdu, steps, {1: "Streak camera / spectrograph"}, "SD2")
        steps.power_ready()
        api._lifecycle().put(OWNER_KEY, None)
        return {"message": "DCAM released and camera outlet verified OFF", "steps": list(steps)}

    def authorize(action, targets):
        payload, rejected = api._mutation_payload(set())
        if rejected is not None:
            return rejected
        if payload:
            return jsonify(success=False, error="This action accepts an empty request"), 400
        return api._approval_or_response(action, targets, {}, f"vd2.dcam.{action}", set())

    @routes.before_request
    def protect_dcam_owner():
        path = request.path.removeprefix(routes.url_prefix)
        if path.startswith(("/dcam/", "/workspace/")) or path in {"/lifecycle", "/lifecycle/log", "/protocol/state"}:
            return None
        if owner() is None:
            return None
        if path == "/deinitialize" and request.method == "POST":
            return dcam_unprepare()
        return jsonify(success=False, code="VD2_DCAM_ACTIVE",
                       error="DCAM readout owns VD2. Use the DCAM page to Unprepare."), 409

    @routes.get("/dcam/state")
    def dcam_state():
        marked = owner()
        ready = marked == this_process() and readout.camera is not None
        job = api._lifecycle().get("job") or {}
        operation = {name: job.get(name) for name in ("status", "phase", "error")} if job.get("intent") == INTENT else None
        return jsonify(success=True, owned=marked is not None, ready=ready, live=ready and readout.live,
                       model=readout.device.model if ready and readout.device else None,
                       operation=operation)

    @routes.post("/dcam/prepare")
    def dcam_prepare():
        denied = authorize("prepare", [api._target(api.VD2_PDU_DEVICE, "set_channels_states")])
        if denied is not None:
            return denied
        job = api._lifecycle().get("job") or {}
        if job.get("status") == "running" and job.get("intent") != INTENT:
            return jsonify(success=False, error="Wait for the current VD2 operation to finish"), 409
        if (owner() is None and job.get("status") != "running"
                and (job.get("operation"), job.get("status")) != ("shutdown", "completed")):
            return jsonify(success=False, error="Complete the standard VD2 Unprepare before selecting DCAM"), 409
        if owner() is not None and job.get("status") != "running":
            return jsonify(success=False, error="Unprepare the previous DCAM session before preparing again"), 409
        return api._start_lifecycle("prepare", prepare, intent=INTENT)

    @routes.post("/dcam/unprepare")
    def dcam_unprepare():
        denied = authorize("unprepare", [api._target(api.VD2_PDU_DEVICE, "set_channels_states")])
        if denied is not None:
            return denied
        if owner() is None:
            return jsonify(success=False, error="DCAM does not own the camera outlet"), 409
        return api._start_lifecycle("shutdown", shutdown, intent=INTENT)

    def control(action, fn):
        denied = authorize(action, [api._target(api.STREAK_DEVICE, f"DCAM_{action}")])
        if denied is not None:
            return denied
        if owner() != this_process() or readout.camera is None:
            return jsonify(success=False, error="Prepare DCAM first"), 409
        try:
            return jsonify(success=True, **(fn() or {}))
        except Exception as exc:
            return jsonify(success=False, error=api._control_error(exc)), 503

    @routes.post("/dcam/live")
    @api._serialized_vd2_mutation
    def dcam_live():
        def start():
            check_dark()
            readout.call(readout.start)
        return control("live", start)

    @routes.post("/dcam/stop")
    @api._serialized_vd2_mutation
    def dcam_stop():
        return control("stop", lambda: readout.call(readout.stop))

    @routes.post("/dcam/blank")
    @api._serialized_vd2_mutation
    def dcam_blank():
        def record():
            check_dark()
            now = datetime.now()
            root = Path(api._dcam_output_root)
            from treatment_api import _ensure_within_allowed_root
            folder = root / now.strftime("%Y%m%d") / "DCAM"
            _ensure_within_allowed_root(str(folder))
            folder.mkdir(parents=True, exist_ok=True)
            output = folder / f"BRUIT-{now:%H%M%S}-{uuid4().hex[:8]}.npz"
            return readout.call(readout.blank, output)
        return control("blank", record)

    @routes.get("/dcam/preview")
    def dcam_preview():
        if not readout.live or owner() != this_process():
            return jsonify(success=True, frame=None)
        try:
            frame = readout.call(readout.read_frame)
            return jsonify(success=True, frame=frame)
        except RuntimeError as exc:
            if str(exc) == "A DCAM operation is still in progress":
                return jsonify(success=True, frame=readout.preview)
            return jsonify(success=False, error=str(exc)), 503
        except Exception as exc:
            return jsonify(success=False, error=api._control_error(exc)), 503
