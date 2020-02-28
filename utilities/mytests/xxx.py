from dataclasses import dataclass

@dataclass(order=True, frozen=False)
class AxisState:
    name: str
    position: float
    limits: tuple
    status: int = 0
from json import dumps, loads

a = AxisState('a', 0, (0, 100))
res = {'a':100, 2: (100), 'axes': a}
json_str = dumps(repr(res)).encode('utf-8')
back = loads(json_str)
print(json_str, back, eval(back))



