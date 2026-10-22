"""Persist only the new local archive DB settings and a current-user login hook."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import winreg

BASE = Path(r'F:\ELYSE_PostgreSQL')
sys.path.insert(0, str(BASE / 'python-packages'))
import psycopg
from psycopg import sql

config = json.loads((BASE / 'secrets/admin.json').read_text())
with psycopg.connect(**config, autocommit=True) as conn:
    for name, value in dict(listen_addresses='127.0.0.1', port='5432', timezone='UTC',
                            max_connections='30', shared_buffers='128MB',
                            logging_collector='on', log_directory='F:/ELYSE_PostgreSQL/logs').items():
        conn.execute(sql.SQL('ALTER SYSTEM SET {} = {}').format(sql.Identifier(name), sql.Literal(value)))
    conn.execute('SELECT pg_reload_conf()')
source = Path(__file__).with_name('start_acq_postgres.pyw')
destination = BASE / source.name
if destination.exists() and destination.read_bytes() != source.read_bytes():
    raise RuntimeError('Existing startup helper differs; refusing overwrite')
shutil.copy2(source, destination)
pythonw = Path(sys.executable).with_name('pythonw.exe')
command = f'"{pythonw}" "{destination}"'
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
    try:
        previous, _ = winreg.QueryValueEx(key, 'ELYSEPostgreSQL')
    except FileNotFoundError:
        previous = None
    if previous is not None and previous != command:
        raise RuntimeError('Existing startup registration differs; refusing overwrite')
    winreg.SetValueEx(key, 'ELYSEPostgreSQL', 0, winreg.REG_SZ, command)
subprocess.run([sys.executable, str(destination)], check=True,
               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
print(json.dumps(dict(configured=True, startup='current_user_logon', data=str(BASE / 'data'),
                      existing_cluster_only=True, hardware_commands_sent=False)))
