from json import dumps, loads
from enum import Enum, auto
from dataclasses import dataclass
from devices.interfaces import DeviceType


print(DeviceType.CLIENT.__str__())

@dataclass
class A:
    type: DeviceType = DeviceType.CLIENT

a = A()

a_str = str(a)

a_json = dumps(a_str).encode('utf-8')

back_str = loads(a_json)

try:
    back = eval(back_str)
    assert back.type is DeviceType.CLIENT
    c = back
except Exception as e:
    print(e)
