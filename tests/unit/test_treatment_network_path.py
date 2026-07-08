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
    calls = {"copy_count": 0}

    def fake_copy(local_path, smb_path, progress_callback=None):
        calls["copy"] = (str(local_path), smb_path)
        calls["copy_count"] += 1
        if progress_callback:
            progress_callback(2)
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
    assert calls["copy_count"] == 1
    assert calls["copy"][1].startswith("smb://10.20.30.202/e/DATA_VD2/run/~")
    assert calls["copy"][1].endswith(".tmp")
    assert calls["replace"][1] == r"\\10.20.30.202\e\DATA_VD2\run\ABS13113.h5"


def test_copy_local_file_to_smb_atomic_reports_locked_target(monkeypatch, tmp_path):
    source = tmp_path / "ABS13113.h5"
    source.write_bytes(b"h5")
    removed = {}
    monkeypatch.setenv("PYCONLYSE_SMB_LOCK_RETRIES", "1")

    def fake_copy(_local_path, _smb_path, progress_callback=None):
        if progress_callback:
            progress_callback(2)
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

    assert removed["path"].startswith(r"\\10.20.30.202\e\DATA_VD2\run\~")


def test_copy_smb_file_to_local_retries_locked_source(monkeypatch, tmp_path):
    target = tmp_path / "BASE13115.his"
    calls = {"open": 0, "sleep": 0}
    monkeypatch.setenv("PYCONLYSE_SMB_LOCK_RETRIES", "2")
    monkeypatch.setenv("PYCONLYSE_SMB_LOCK_RETRY_DELAY", "0")
    monkeypatch.setattr(network_path.time, "sleep", lambda _delay: calls.__setitem__("sleep", calls["sleep"] + 1))

    class FakeSource:
        def __init__(self):
            self._chunks = [b"his", b""]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size):
            return self._chunks.pop(0)

    class FakeSmbClient:
        def open_file(self, _path, mode="rb"):
            assert mode == "rb"
            calls["open"] += 1
            if calls["open"] == 1:
                raise OSError(
                    "[NtStatus 0xc0000043] The process cannot access the file because it is being used by another process"
                )
            return FakeSource()

    monkeypatch.setattr(network_path, "_smbclient", lambda: FakeSmbClient())

    written = network_path.copy_smb_file_to_local(
        "smb://10.20.30.202/e/DATA_VD2/run/BASE13115.his",
        target,
    )

    assert written == 3
    assert target.read_bytes() == b"his"
    assert calls == {"open": 2, "sleep": 1}


def test_smb_listdir_retries_credit_exhaustion(monkeypatch):
    calls = {"scandir": 0, "reset": 0, "sleep": 0}
    monkeypatch.setenv("PYCONLYSE_SMB_RETRIES", "2")
    monkeypatch.setenv("PYCONLYSE_SMB_RETRY_DELAY", "0")
    monkeypatch.setattr(network_path.time, "sleep", lambda _delay: calls.__setitem__("sleep", calls["sleep"] + 1))

    class FakeStat:
        st_size = 5

    class FakeEntry:
        name = "ABS001.h5"

        def is_file(self):
            return True

        def is_dir(self):
            return False

        def stat(self):
            return FakeStat()

    class FakeSmbClient:
        def scandir(self, _path):
            calls["scandir"] += 1
            if calls["scandir"] == 1:
                raise RuntimeError("Request requires 1 credits but only 0 credits are available")
            return [FakeEntry()]

        def reset_connection_cache(self):
            calls["reset"] += 1

    fake_client = FakeSmbClient()
    monkeypatch.setattr(network_path, "_smbclient", lambda: fake_client)

    listing = list(network_path.smb_listdir("smb://10.20.30.202/e/DATA_VD2/run"))

    assert listing == [{
        "name": "ABS001.h5",
        "path": "smb://10.20.30.202/e/DATA_VD2/run/ABS001.h5",
        "is_dir": False,
        "is_file": True,
        "size_bytes": 5,
    }]
    assert calls == {"scandir": 2, "reset": 1, "sleep": 1}


def test_smb_to_local_path_maps_posix_prefix(monkeypatch, tmp_path):
    monkeypatch.setenv("PYCONLYSE_SMB_LOCAL_MAP", f"smb://10.20.30.202/e/={tmp_path}")

    mapped = network_path.smb_to_local_path(
        "smb://10.20.30.202/e/DATA_VD2/run/ABS001.h5"
    )

    assert mapped == str(tmp_path / "DATA_VD2" / "run" / "ABS001.h5")
    assert network_path.is_mapped_smb_path(
        "smb://10.20.30.202/e/DATA_VD2/run/ABS001.h5"
    )


def test_smb_to_local_path_maps_windows_prefix(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_SMB_LOCAL_MAP", r"smb://10.20.30.202/e/=E:\\")

    mapped = network_path.smb_to_local_path(
        "smb://10.20.30.202/e/DATA_VD2/run/ABS001.h5"
    )

    assert mapped == network_path.ntpath.normpath(r"E:\\DATA_VD2\run\ABS001.h5")


def test_smb_to_local_path_uses_default_windows_e_drive_map(monkeypatch):
    monkeypatch.delenv("PYCONLYSE_SMB_LOCAL_MAP", raising=False)
    monkeypatch.setattr(network_path.os.path, "isdir", lambda path: path == "E:\\")

    mapped = network_path.smb_to_local_path(
        "smb://10.20.30.202/e/DATA_VD2/run/ABS001.h5"
    )

    assert mapped == network_path.ntpath.normpath(r"E:\DATA_VD2\run\ABS001.h5")
