from dataclasses import dataclass


@dataclass
class A:
    a: int = 2
    b: str = 'sdf'

a = A()
for field in a.__annotations__:
    print(getattr(a, field))
from time import sleep
b = True
i = 0
while b:
    if i>100:
        break
    i += 1

print('Doine')