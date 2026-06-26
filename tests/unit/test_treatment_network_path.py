import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import treatment_network_path as network_path


def test_copy_local_file_to_smb_atomic_replaces_target(monkeypatch, tmp_path):
    source = tmp_path / "ABS13113.h5"
    source.write_bytes(b"h5")
    calls = {}

    def fake_copy(local_path, smb_path):
        calls["copy"] = (str(local_path), smb_path)
        return 2

    class FakeSmbClient:
        def replace(self, src, dst):
            calls["replace"] = (src, dst)

    monkeypatch.setattr(network_path, "copy_local_file_to_smb", fake_copy)
    monkeypatch.setattr(network_path, "_smbclient", lambda: FakeSmbClient())

    written = network_path.copy_local_file_to_smb_atomic(
        source,
        "smb://10.20.30.202/e/DATA_VD2/run/ABS13113.h5",
    )

    assert written == 2
    assert calls["copy"][1].startswith(
        "smb://10.20.30.202/e/DATA_VD2/run/.ABS13113.h5.pyconlyse-"
    )
    assert calls["copy"][1].endswith(".tmp")
    assert calls["replace"][1] == r"\\10.20.30.202\e\DATA_VD2\run\ABS13113.h5"


def test_copy_local_file_to_smb_atomic_reports_locked_target(monkeypatch, tmp_path):
    source = tmp_path / "ABS13113.h5"
    source.write_bytes(b"h5")
    removed = {}

    def fake_copy(_local_path, _smb_path):
        return 2

    class FakeSmbClient:
        def replace(self, _src, _dst):
            raise OSError(
                "[NtStatus 0xc0000043] The process cannot access the file because it is being used by another process"
            )

        def remove(self, path):
            removed["path"] = path

    monkeypatch.setattr(network_path, "copy_local_file_to_smb", fake_copy)
    monkeypatch.setattr(network_path, "_smbclient", lambda: FakeSmbClient())

    with pytest.raises(ValueError, match="SMB target is locked by another process"):
        network_path.copy_local_file_to_smb_atomic(
            source,
            "smb://10.20.30.202/e/DATA_VD2/run/ABS13113.h5",
        )

    assert removed["path"].startswith(r"\\10.20.30.202\e\DATA_VD2\run\.ABS13113.h5.pyconlyse-")
