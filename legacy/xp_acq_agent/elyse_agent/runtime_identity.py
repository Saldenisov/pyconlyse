"""Cold runtime identity; Python 3.4, no Git or deployment-attestation claim."""
import hashlib
import os
import uuid


RUNTIME_PROTOCOL_VERSION = 2
SOURCE_MODULES = (
    "__init__.py", "acquisition_backend.py", "acquisition_gui.py", "acquisition_http.py",
    "acquisition_runtime.py", "acquisition_startup.py", "acquisition_procedures.py", "hardware_tasks.py",
    "acquisition_ht_shutdown.py", "hardware_plan.py", "input_tasks.py", "transforms.py", "errors.py",
    "chroma_focal_stop.py", "chroma_focal_command.py", "acquisition_stage_model.py",
    "acquisition_stage_execution.py", "acquisition_cooling_trip.py", "runtime_identity.py",
    "acquisition_recovery.py",
    "acquisition_supervisor.py", "acquisition_command_admission.py",
    "acquisition_source_controls.py", "acquisition_impulsion.py",
    "acquisition_ht_voltage.py", "acquisition_outer_stop.py",
    "acquisition_counter_timing.py",
)
SOURCE_PATHS = ("acquisition_server.pyw",) + tuple("elyse_agent/" + name for name in SOURCE_MODULES) + (
    "data/calibration_map.csv", "data/ni6602_timing.csv", "data/modulator_stage_catalog.json",
)


def source_fingerprint(root=None):
    """Hash installed source/data bytes, independent of checkout path/time.

    This identifies the files present at boot, not the loaded bytecode, Git
    commit, device firmware, configuration, secret, or deployed qualification.
    The explicit package closure excludes runtime journals and telemetry.
    """
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    digest = hashlib.sha256()
    for relative in sorted(SOURCE_PATHS):
        with open(os.path.join(root, *relative.split("/")), "rb") as source:
            raw = source.read()
        name = relative.encode("utf-8")
        digest.update(str(len(name)).encode("ascii") + b":" + name)
        digest.update(str(len(raw)).encode("ascii") + b":" + raw)
    return digest.hexdigest()


def new_runtime_identity():
    return dict(runtime_protocol_version=RUNTIME_PROTOCOL_VERSION,
                session_id=uuid.uuid4().hex, build_id=source_fingerprint())


def valid_hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(character in "0123456789abcdef" for character in value))
