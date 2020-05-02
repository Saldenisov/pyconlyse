from typing import NewType

N = NewType('N', str)
a = N('a')

b = {'a': 2}

if 'b' is a:
    print(1)