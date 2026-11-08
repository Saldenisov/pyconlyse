import importlib.util
import json
from pathlib import Path
import socket

import numpy as np
import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "bin/diagnostics/replay_laser_centering.py"
spec = importlib.util.spec_from_file_location("offline_centering_replay", SCRIPT)
replay_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay_module)


def archive(folder, name, *, duplicate=False, exposure=100000):
    yy, xx = np.indices((101, 101), dtype=float)
    rng = np.random.default_rng(1 if "before" in name else 2)
    image = 150 * np.exp(-.5 * (((xx - 50) / 11) ** 2 + ((yy - 50) / 15) ** 2))
    frames = np.asarray([image + rng.normal(0, .03, image.shape) for _ in range(7)])
    if duplicate:
        frames[1] = frames[0]
    np.savez_compressed(folder / (name + ".npz"), frames=frames)
    (folder / (name + ".json")).write_text(json.dumps({
        "active_point": "point4", "camera": {"width": 101, "height": 101,
        "center_gravity_threshold": 30, "exposure_time": exposure, "gain": 2},
    }), encoding="utf-8")


def test_saved_frame_replay_is_offline_and_does_not_claim_hardware_alignment(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("offline replay must not connect to equipment or network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    source = tmp_path / "source"
    source.mkdir()
    archive(source, "p4-before-coarse")
    archive(source, "p4-after-coarse")
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    report = replay_module.replay(source, tmp_path / "output")
    assert len(report["records"]) == 2
    for record in report["records"].values():
        assert record["alignment_verified"] is False
        assert record["hardware_return_tested"] is False
        assert record["aperture_pair_checked"] is False
        groups = record["disjoint_frame_indices"]
        assert sorted(i for group in groups for i in group) == list(range(7))
        assert record["within_frame_verification"]["centering_passed"] is True
        assert record["within_frame_verification"]["ellipticity_passed"] is False
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}


def test_repeated_archived_frame_is_not_independent_evidence(tmp_path):
    archive(tmp_path, "duplicate", duplicate=True)
    with pytest.raises(ValueError, match="duplicated frames"):
        replay_module.replay(tmp_path, tmp_path / "output")


def test_exposure_change_is_not_accepted_as_a_mirror_improvement(tmp_path):
    archive(tmp_path, "p4-before-coarse", exposure=50000)
    archive(tmp_path, "p4-after-coarse", exposure=100000)
    with pytest.raises(ValueError, match="confounded"):
        replay_module.replay(tmp_path, tmp_path / "output")
