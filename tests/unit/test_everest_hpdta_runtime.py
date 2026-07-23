import json
import sys
from pathlib import Path
from subprocess import CompletedProcess


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from everest_hpdta_runtime import EverestHpdtaRuntime


def test_runtime_state_parses_everest_process_status(monkeypatch, tmp_path):
    key = tmp_path / "id_ed25519"
    key.write_text("key", encoding="ascii")
    monkeypatch.setenv("PYCONLYSE_EVERST_SSH_KEY", str(key))

    def runner(command, **kwargs):
        assert command[-1].endswith("ConvertTo-Json -Compress")
        return CompletedProcess(command, 0, json.dumps({"remoteex_running": True, "hpdta_running": False}), "")

    runtime = EverestHpdtaRuntime(runner=runner)
    assert runtime.state() == {"remoteex_running": True, "hpdta_running": False}
