"""Best-effort receiver lifecycle/native-fault evidence, outside alarm history."""
from datetime import datetime, timezone
import faulthandler
import json
import os
from pathlib import Path
import sys
import uuid


def rotate(path, size=2*1024*1024):
    if path.exists() and path.stat().st_size >= size:
        os.replace(path, path.with_suffix(path.suffix + '.previous'))


def run_diagnosed(run, classes, directory=None):
    directory = Path(directory or r'F:\ELYSE_PostgreSQL\recovery')
    session = uuid.uuid4().hex
    fault_file = None
    previous_fault_handler = faulthandler.is_enabled()

    def event(kind, **fields):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory/'receiver_lifecycle.jsonl'
            rotate(path)
            with path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),
                    event=kind, pid=os.getpid(), session=session, **fields)) + '\n')
        except Exception:
            pass  # Diagnostics cannot prevent receiver startup or shutdown.

    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory/'receiver_native_fault.log'
        rotate(path)
        fault_file = path.open('a', encoding='utf-8')
        faulthandler.enable(file=fault_file, all_threads=True)
    except Exception:
        if fault_file is not None:
            fault_file.close()
            fault_file = None
    event('start', native_fault_capture=fault_file is not None)
    try:
        result = run(classes)
    except BaseException as error:
        code = error.code if isinstance(error, SystemExit) else 1
        event('exit', code=code if isinstance(code, (int, type(None))) else 1,
              error=type(error).__name__)
        raise
    else:
        event('exit', code=0)
        return result
    finally:
        if fault_file is not None:
            try:
                if previous_fault_handler:
                    faulthandler.enable(file=sys.stderr, all_threads=True)
                else:
                    faulthandler.disable()
            except Exception:
                pass
            finally:
                try:
                    fault_file.close()
                except Exception:
                    pass
