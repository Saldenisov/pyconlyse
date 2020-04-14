import logging
import sqlite3 as sq3
from hashlib import md5
from pathlib import Path
from time import sleep
from typing import Tuple, Any, Iterable, Union

module_logger = logging.getLogger(__name__)


def db_check_update(parent, tick: int, DB_path: Path):
    hash_init = calc_db_hash(DB_path)
    while parent.active:
        sleep(tick)
        h = calc_db_hash(DB_path)
        if hash_init != h:
            hash_init = h
            parent.update_config('database is changed externally')


def db_execute_select(connection: sq3.Connection, command: str, multiple=False) -> Tuple[Any, bool]:
    #TODO: modify so it return res, comments as a Tuple
    try:
        cur = connection.cursor()
        cur.execute(command)
        if not multiple:
            value = cur.fetchone()
            if len(value) == 1:
                value = value[0]
        else:
            value = (value[0] for value in cur.fetchall())
        comments = ''
    except (sq3.OperationalError, KeyError) as e:
        module_logger.error(e)
        value = False
        comments = f'db_execute_select: {e}'
    finally:
        return value, comments


def db_execute_insert(connection: sq3.Connection, command: str,
                      parameters: Union[Iterable, Iterable[Iterable]],
                      multiple=False) -> Any:
    try:
        cur = connection.cursor()
        if not multiple:
            cur.execute(command, parameters)
        else:
            cur.executemany(command, parameters)
        connection.commit()
        return True, ''
    except (sq3.OperationalError, sq3.Error) as e:
        module_logger.error(e)
        raise e


def db_create_connection(DBfile: Path) -> sq3.Connection:
        """create tests_devices database connection to the SQLite database
            specified by the db_file
        :param db_file: database file
        :return: Connection objector None
        """
        try:
            conn: sq3.Connection = sq3.connect(str(DBfile))
            return conn
        except sq3.Error as e:
            module_logger.error(e)
            raise e


def db_close_conn(conn: sq3.Connection):
    try:
        conn.close()
    except Exception as e:
        module_logger.error(e)
        raise e


def calc_db_hash(DB_path: Path):
        """
        This function tales tests_devices Path to database sqlite
        It calc the hash function, to use later if database is changed
        externally
        :param DB_path:
        :return: hash value of the file
        """
        hash_md5 = md5()
        with open(DB_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()