import platform
from os import path
from pathlib import Path


if platform.system() == "Windows":
    cur_dir = Path(path.dirname(__file__))
    arch_type = "win64" if "64" in platform.architecture()[0] else "win32"
    if arch_type == 'win64':
        path_dll = cur_dir / 'win64' / 'libximc.dll'
    elif arch_type == 'win32':
        path_dll = cur_dir / 'win32' / 'libximc.dll'

else:
    raise Exception('Only Windows is available at this moment')



from .myximc import *