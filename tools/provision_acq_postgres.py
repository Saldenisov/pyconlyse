"""Explicit local PostgreSQL provisioning. All installation state stays on F:."""
import json
from pathlib import Path
import secrets
import subprocess
import sys

BASE = Path(r'F:\ELYSE_PostgreSQL')
BIN = BASE / '17.11' / 'pgsql' / 'bin'
DATA = BASE / 'data'
PRIVATE = BASE / 'secrets'
CONFIG = PRIVATE / 'archive.json'


def main():
    if DATA.exists() or CONFIG.exists():
        raise RuntimeError('Existing cluster/configuration: refusing to overwrite')
    if not PRIVATE.is_dir():
        raise RuntimeError('Create and restrict the private directory before provisioning')
    subprocess.run(['powershell.exe', '-NoProfile', '-File',
                    str(Path(__file__).with_name('secure_acq_postgres_storage.ps1'))], check=True,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    sys.path.insert(0, str(BASE / 'python-packages'))
    import psycopg
    from psycopg import sql
    admin_password, app_password = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
    password_file = PRIVATE / 'initdb-password.txt'
    password_file.write_text(admin_password + '\n', encoding='utf-8')
    admin = dict(host='127.0.0.1', port=5432, dbname='postgres',
                 user='elyse_pg_admin', password=admin_password)
    (PRIVATE / 'admin.json').write_text(json.dumps(admin), encoding='utf-8')
    try:
        subprocess.run([str(BIN / 'initdb.exe'), '-D', str(DATA), '-U', admin['user'],
                        '--pwfile', str(password_file), '--auth=scram-sha-256',
                        '--encoding=UTF8', '--locale=C'], check=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    finally:
        password_file.unlink(missing_ok=True)
    options = ('-h 127.0.0.1 -p 5432 -c timezone=UTC -c max_connections=30 '
               '-c shared_buffers=128MB -c logging_collector=on '
               '-c log_directory=F:/ELYSE_PostgreSQL/logs')
    subprocess.run([str(BIN / 'pg_ctl.exe'), 'start', '-D', str(DATA), '-w', '-t', '30',
                    '-l', str(BASE / 'logs' / 'startup.log'), '-o', options], check=True,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    with psycopg.connect(**admin, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE ROLE elyse_archive LOGIN PASSWORD {}').format(sql.Literal(app_password)))
        conn.execute('CREATE DATABASE elyse_telemetry OWNER elyse_archive')
    config = dict(host='127.0.0.1', port=5432, dbname='elyse_telemetry',
                  user='elyse_archive', password=app_password,
                  driver_path=str(BASE / 'python-packages'),
                  spool_path=str(BASE / 'spool' / 'ingress.sqlite3'))
    CONFIG.write_text(json.dumps(config, indent=2), encoding='utf-8')
    print(json.dumps(dict(result='READY', config=str(CONFIG), data=str(DATA),
                          listen='127.0.0.1:5432', credentials_printed=False)))


if __name__ == '__main__':
    main()
