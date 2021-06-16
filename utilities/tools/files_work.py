from pathlib import Path
from typing import Any
from time import sleep

def write_to_file_unique(file_path: Path, data: Any) -> bool:
    try:
        sleep(0.01)
        with open(file_path, 'r+') as opened_file:
            write = False
            data_str = str(data)
            if opened_file.readable():
                line = opened_file.readline()
                if line != data_str:
                    write = True
            else:
                write = True
            if write:
                opened_file.seek(0)
                opened_file.write(data_str)
                opened_file.truncate()
        return True
    except Exception as e:
        return False
