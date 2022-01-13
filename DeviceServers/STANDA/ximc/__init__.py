import platform
from os import path
from pathlib import Path


ximc_dir = Path(path.dirname(__file__))

if platform.system() == "Windows":
    arch_type = "win64" if "64" in platform.architecture()[0] else "win32"
    if arch_type == 'win64':
        path_dll = ximc_dir / 'win64' / 'libximc.dll'
    elif arch_type == 'win32':
        path_dll = ximc_dir / 'win32' / 'libximc.dll'
elif platform.system() == "Linux":
    arch_type = 'win64'
    path_dll = Path('/usr/lib/')

else:
    raise Exception('Only Windows/Linux is available at this moment')

try:
    from DeviceServers.STANDA.ximc.myximc import *
except ModuleNotFoundError:
    from myximc import *
