"""Synthetic files only: conversion, phase identity and raw-data preservation."""
import hashlib
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest
from utilities.dataio.h5_opener import H5Opener

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
from vd2_measurement_protocol import PhaseRequest, Vd2ProtocolError
from vd2_sequence_processing import check_new_sequence, process_saved_sequence
from vd2_sequence_processing import _publish_verified_h5
from vd2_sequence_processing import retire_source_his


def request_file(tmp_path, phase="BRUIT", frames=3):
    source = tmp_path / "phase.his"
    header = ('ScalingXScalingFile= Other,ScalingXScale=1,ScalingXUnit="nm",'
              'ScalingYScale=1,ScalingYUnit="ns",').encode()
    binary = bytearray(64)
    for start, value in ((2, len(header)), (4, 2), (6, 3), (12, 2), (14, frames)):
        binary[start:start + 2] = value.to_bytes(2, "little")
    with source.open("wb") as handle:
        handle.write(binary)
        handle.write(header)
        for index in range(frames):
            handle.write((np.arange(6, dtype=np.int16) + index * 100).tobytes())
            handle.write(bytes(64))
    return PhaseRequest(phase, frames, str(tmp_path), "synthetic", str(source))


@pytest.mark.parametrize(
    "phase,stored", [("BRUIT", "NOISE"), ("BASE", "BASE"), ("ABSORPTION", "ABS")]
)
def test_verified_h5_replaces_his_without_losing_raw_frames_or_source_provenance(tmp_path, phase, stored):
    request = request_file(tmp_path, phase)
    source = Path(request.his_path)
    before = hashlib.sha256(source.read_bytes()).digest()
    result = process_saved_sequence(request)
    output = Path(result["h5_path"])
    assert result["frame_count"] == 3
    assert result["source_his_retained"] is True
    assert hashlib.sha256(source.read_bytes()).digest() == before
    with h5py.File(output, "r") as handle:
        assert handle["raw_data"].shape == (3, 2, 3)
        assert handle["metadata"].attrs["phase"] == stored
        assert handle["metadata"].attrs["lossless_verified"]
        assert handle["metadata"].attrs["source_his_sha256"] == before.hex()
        assert np.asarray(handle["map_selection/included"]).all()
    opener = H5Opener()
    assert opener.read_critical_info(output).number_maps == 3
    for index in range(3):
        assert np.array_equal(opener.read_map(output, index)[0].data,
                              (np.arange(6).reshape(3, 2) + index * 100).T)
    h5_before = output.read_bytes()
    cleanup = retire_source_his(request, result)
    assert cleanup['source_his_retained'] is False
    assert cleanup['source_his_cleanup_status'] == 'removed'
    assert not source.exists()
    assert output.read_bytes() == h5_before
    assert not list(tmp_path.glob(".vd2-convert-*"))


@pytest.mark.parametrize("extension", [".his", ".h5"])
def test_preflight_refuses_existing_phase_files(tmp_path, extension):
    source = tmp_path / "new.his"
    source.with_suffix(extension).write_bytes(b"keep")
    request = PhaseRequest("BASE", 3, str(tmp_path), "test", str(source))
    with pytest.raises(Vd2ProtocolError, match="choose a new run name"):
        check_new_sequence(request)


def test_existing_h5_is_never_replaced(tmp_path):
    request = request_file(tmp_path)
    output = Path(request.his_path).with_suffix(".h5")
    output.write_bytes(b"existing data")
    with pytest.raises(Vd2ProtocolError, match="Existing H5 does not match this HIS; both files retained"):
        process_saved_sequence(request)
    assert output.read_bytes() == b"existing data"
    assert Path(request.his_path).exists()


def test_publication_copies_verified_bytes_without_replacing_existing_output(tmp_path):
    staged = tmp_path / 'private' / 'phase.h5'
    staged.parent.mkdir(); staged.write_bytes(b'verified H5 bytes')
    output = tmp_path / 'phase.h5'
    _publish_verified_h5(staged, output)
    assert output.read_bytes() == staged.read_bytes()
    output.write_bytes(b'earlier output')
    with pytest.raises(FileExistsError):
        _publish_verified_h5(staged, output)
    assert output.read_bytes() == b'earlier output'
    assert not list(tmp_path.glob('.vd2-publish-*'))


def test_wrong_frame_count_preserves_his_without_publishing_h5(tmp_path):
    original = request_file(tmp_path)
    request = PhaseRequest("BRUIT", 4, original.output_root, "test", original.his_path)
    with pytest.raises(Vd2ProtocolError, match="contains 3 frames; expected 4"):
        process_saved_sequence(request)
    assert Path(request.his_path).exists()
    assert not Path(request.his_path).with_suffix(".h5").exists()


def test_corrupt_conversion_is_not_published_and_his_survives(tmp_path, monkeypatch):
    from treatment_service import TreatmentDataService
    request = request_file(tmp_path)
    original = TreatmentDataService.convert_file_to_h5

    def corrupt(self, source, output, **kwargs):
        original(self, source, output, **kwargs)
        with h5py.File(output, "r+") as handle:
            handle["raw_data"][2, 0, 0] = -123

    monkeypatch.setattr(TreatmentDataService, "convert_file_to_h5", corrupt)
    with pytest.raises(Vd2ProtocolError, match="frame 3 verification failed"):
        process_saved_sequence(request)
    assert Path(request.his_path).exists()
    assert not Path(request.his_path).with_suffix(".h5").exists()
    assert not list(tmp_path.glob(".vd2-convert-*"))


@pytest.mark.parametrize('changed', ['his', 'h5'])
def test_cleanup_refuses_a_changed_source_or_verified_container(tmp_path, changed):
    request = request_file(tmp_path)
    result = process_saved_sequence(request)
    source = Path(request.his_path)
    target = source if changed == 'his' else Path(result['h5_path'])
    with target.open('ab') as handle: handle.write(b'changed')
    with pytest.raises(Vd2ProtocolError, match='changed'):
        retire_source_his(request, result)
    assert source.exists()


def test_cleanup_does_not_remove_source_without_verification(tmp_path):
    request = request_file(tmp_path)
    with pytest.raises(Vd2ProtocolError, match='provenance'):
        retire_source_his(request, {})
    assert Path(request.his_path).is_file()


def test_delete_failure_reports_retained_his_and_keeps_valid_h5(tmp_path, monkeypatch):
    request = request_file(tmp_path); result = process_saved_sequence(request)
    original = Path.unlink
    def locked(path, *args, **kwargs):
        if path == Path(request.his_path): raise PermissionError('HIS still in use')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', locked)
    cleanup = retire_source_his(request, result)
    assert cleanup['source_his_retained'] is True
    assert 'HIS still in use' in cleanup['cleanup_warning']
    assert Path(request.his_path).is_file()
    assert Path(result['h5_path']).is_file()
