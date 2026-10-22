"""Hidden, idempotent user-login startup; never initializes a new cluster."""
from pathlib import Path
import subprocess

base = Path(__file__).resolve().parent
if base.drive.upper() != 'F:' or not (base / 'data/PG_VERSION').is_file():
    raise RuntimeError('Expected existing PostgreSQL cluster on F:')
binary = base / '17.11/pgsql/bin/pg_ctl.exe'
flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
with (base / 'logs/autostart.log').open('a', encoding='utf-8') as log:
    status = subprocess.run([str(binary), 'status', '-D', str(base / 'data')],
                            stdout=log, stderr=log, creationflags=flags, timeout=10)
    if status.returncode != 0:
        subprocess.run([str(binary), 'start', '-D', str(base / 'data'), '-w', '-t', '30',
                        '-l', str(base / 'logs/startup.log')], check=True, timeout=40,
                       stdout=log, stderr=log, creationflags=flags)
