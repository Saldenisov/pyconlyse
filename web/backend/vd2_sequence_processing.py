"""Lossless post-phase conversion using the Data Treatment H5 format."""

from __future__ import annotations

import os
from multiprocessing import get_context
from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryDirectory
from time import monotonic
from uuid import uuid4

from vd2_measurement_protocol import PhaseRequest, Vd2ProtocolError
from vd2_project_manifest import fingerprint


def check_new_sequence(request: PhaseRequest) -> None:
    """Reject existing phase artifacts before starting another acquisition."""
    source = Path(request.his_path)
    for path in (source, source.with_suffix(".h5")):
        if path.exists():
            raise Vd2ProtocolError(
                f"Phase file already exists; choose a new run name: {path}"
            )


def _publish_verified_h5(staged: Path, output: Path) -> None:
    # A Windows TemporaryDirectory can carry a private DACL. Moving its child
    # out keeps that DACL and can make an administrator-created H5 unreadable
    # by the operator. Create a new sibling with the destination folder's normal
    # inherited permissions; never modify that folder's access policy.
    sibling = output.with_name(f".vd2-publish-{uuid4().hex}.tmp")
    try:
        with sibling.open("xb") as destination, staged.open("rb") as source:
            copyfileobj(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
        # Both paths are on the same volume. Publication remains atomic and
        # fails rather than replacing a destination created by another writer.
        if os.name == "nt":
            sibling.rename(output)
        else:
            os.link(sibling, output)
    finally:
        sibling.unlink(missing_ok=True)


def process_saved_sequence(request: PhaseRequest, progress=None) -> dict:
    # Lazy imports keep passive acquisition status independent of H5 dependencies.
    import h5py
    import numpy as np
    from treatment_service import TreatmentDataService
    from utilities.dataio.hamamatsu_file_opener import HamamatsuFileOpener

    source = Path(request.his_path)
    output = source.with_suffix(".h5")
    report = progress or (lambda _: None)
    opener = HamamatsuFileOpener()
    source_identity = fingerprint(source)
    info = opener.read_critical_info(source)
    count = int(info.number_maps)
    wavelengths = (info.wavelengths if request.spectral_axis_nm is None
                   else np.asarray(request.spectral_axis_nm, dtype=float))
    if wavelengths.shape != (info.wavelengths_length,):
        raise Vd2ProtocolError("Spectral calibration width does not match HIS; HIS retained")
    if count != request.frames_per_his:
        raise Vd2ProtocolError(
            f"HIS contains {count} frames; expected {request.frames_per_his}; "
            "HIS retained"
        )

    def verify(path, start_percent):
        with h5py.File(path, "r") as handle:
            raw = handle["raw_data"]
            expected_shape = (count, info.wavelengths_length, info.timedelays_length)
            if raw.shape != expected_shape or raw.compression != "gzip":
                raise Vd2ProtocolError(
                    "Converted H5 shape/compression is invalid; HIS retained"
                )
            if "metadata" not in handle or (
                "map_selection/included" in handle and not np.all(handle["map_selection/included"][:])
            ):
                raise Vd2ProtocolError("H5 contains an incomplete or cleaned selection; HIS retained")
            for name in ("timedelays", "wavelengths"):
                if not np.array_equal(handle[name], wavelengths if name == "wavelengths" else info.timedelays):
                    raise Vd2ProtocolError(
                        f"Converted {name} differ from HIS; HIS retained"
                    )
            for index in range(count):
                measurement, error = opener.read_map(source, index)
                if measurement is False or not np.array_equal(
                    raw[index], measurement.data
                ):
                    raise Vd2ProtocolError(
                        f"H5 frame {index + 1} verification failed: {error}; "
                        "HIS retained"
                    )
                report(start_percent + (94 - start_percent) * (index + 1) // count)
    def verify_existing():
        try:
            identity = fingerprint(output)
            verify(output, 50)
            return identity
        except Exception as exc:
            raise Vd2ProtocolError(f"Existing H5 does not match this HIS; both files retained: {output}: {exc}") from exc

    if output.exists():
        verified_identity = verify_existing()
    else:
        with TemporaryDirectory(prefix=".vd2-convert-", dir=source.parent) as temporary:
            staged = Path(temporary) / output.name
            TreatmentDataService().convert_file_to_h5(
                source, staged, progress_callback=lambda current, total: report(50 * current // max(1, total)),
            )
            if request.spectral_axis_nm is not None:
                with h5py.File(staged, "r+") as handle:
                    handle["wavelengths"][:] = wavelengths
                    handle["wavelengths"].attrs["unit"] = "nm"
                    handle["metadata"].attrs["spectral_calibration_id"] = request.spectral_calibration_id
            verify(staged, 50)
            with h5py.File(staged, "r+") as handle:
                metadata = handle["metadata"].attrs
                phases = {"BRUIT": "NOISE", "ABSORPTION": "ABS", "BASE": "BASE"}
                metadata["phase"] = phases[request.phase]
                metadata["frames_requested"] = request.frames_per_his
                metadata["lossless_verified"] = True
                metadata["source_his_name"] = source.name
                metadata["source_his_sha256"] = source_identity["sha256"]
                metadata["source_his_size_bytes"] = source_identity["size_bytes"]
                metadata["source_his_retention_policy"] = "delete_after_verified_h5_and_manifest"
            verified_identity = fingerprint(staged)
            try:
                _publish_verified_h5(staged, output)
            except FileExistsError:
                verified_identity = verify_existing()
    if fingerprint(source) != source_identity or fingerprint(output) != verified_identity:
        raise Vd2ProtocolError("HIS or published H5 changed during verification; HIS retained")
    report(100)
    return {"h5_path": str(output), "frame_count": count,
            "lossless_verified": True, "source_his_retained": True,
            "source_his_cleanup_pending": True, "source_his_fingerprint": source_identity,
            "h5_fingerprint": verified_identity}


def _conversion_worker(request, pipe):
    with pipe:
        last_percent = -1

        def report(value):
            nonlocal last_percent
            if value > last_percent:
                pipe.send(("progress", value))
                last_percent = value

        try:
            result = process_saved_sequence(request, report)
        except Exception as exc:
            pipe.send(("error", str(exc)))
        else:
            pipe.send(("result", result))


def process_saved_sequence_in_worker(request, progress):
    """Run HDF5 work outside the camera and Web processes; retain HIS on failure."""
    context = get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    with receive, send:
        process = context.Process(target=_conversion_worker, args=(request, send), name="vd2-his-to-h5")
        process.start()
        send.close()
        try:
            deadline = monotonic() + 1200
            while monotonic() < deadline:
                if receive.poll(0.2):
                    try:
                        kind, value = receive.recv()
                    except EOFError:
                        break
                    if kind == "progress":
                        progress(value)
                    elif kind == "result":
                        return value
                    else:
                        raise Vd2ProtocolError(value)
                elif not process.is_alive():
                    break
            raise Vd2ProtocolError("H5 worker stopped or timed out before verification; HIS retained")
        finally:
            process.join(1)
            if process.is_alive():
                process.terminate()
                process.join(5)
                if process.is_alive():
                    process.kill()
                    process.join(2)
            if not process.is_alive():
                process.close()


def retire_source_his(request: PhaseRequest, conversion: dict) -> dict:
    """Remove only the unchanged source of a durably recorded, verified H5."""
    source = Path(request.his_path)
    output = source.with_suffix(".h5")
    if (conversion.get("lossless_verified") is not True
            or str(output) != conversion.get("h5_path")
            or not conversion.get("h5_fingerprint") or not conversion.get("source_his_fingerprint")):
        raise Vd2ProtocolError("Verified conversion provenance is missing; HIS retained")
    if fingerprint(output) != conversion["h5_fingerprint"]:
        raise Vd2ProtocolError("Verified H5 changed before source cleanup; HIS retained")
    if not source.exists():
        return {"source_his_retained": False, "source_his_cleanup_pending": False,
                "source_his_cleanup_status": "already_absent"}
    if fingerprint(source) != conversion["source_his_fingerprint"]:
        raise Vd2ProtocolError("HIS changed after conversion; source retained")
    try:
        source.unlink()
    except OSError as exc:
        return {"source_his_retained": True, "source_his_cleanup_pending": False,
                "source_his_cleanup_status": "retained", "cleanup_warning": f"H5 verified, but HIS could not be removed: {exc}"}
    return {"source_his_retained": False, "source_his_cleanup_pending": False,
            "source_his_cleanup_status": "removed"}
