import logging
import sqlite3 as sq3
from hashlib import md5
from pathlib import Path
from time import sleep

module_logger = logging.getLogger(__name__)


def check_DB_update(parent, tick: int, DB_path: Path):
    hash_init = calc_DB_hash(DB_path)
    while parent.active:
        sleep(tick)
        h = calc_DB_hash(DB_path)
        if hash_init != h:
            hash_init = h
            parent.update_config('DB is changed externally')


def executeDBcomm(cur, command: str):
    if cur:
        try:
            cur.execute(command)
            return cur.fetchone()
        except sq3.OperationalError as e:
            module_logger.error(e)
    else:
        return None


def create_connectionDB(DBfile: Path):
        """ create tests_hardware database connection to the SQLite database
            specified by the db_file
        :param db_file: database file
        :return: Connection object or None
        """
        try:
            conn = sq3.connect(str(DBfile))
            cur = conn.cursor()
        except sq3.Error as e:
            module_logger.error(e)
        finally:
            return conn, cur


def close_connDB(conn: sq3.Connection, logger=None):
    try:
        conn.close()
        conn = None
    except Exception as e:
        module_logger.error(e)
    finally:
        return conn


def calc_DB_hash(DB_path: Path):
        """
        This function tales tests_hardware Path to DB sqlite
        It calc the hash function, to use later if DB is changed
        externally
        :param DB_path:
        :return: hash value of the file
        """
        hash_md5 = md5()
        with open(DB_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()