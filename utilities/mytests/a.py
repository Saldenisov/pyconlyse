from enum import Enum

class A( Enum):
    C = 'C'
    B = 'B'


if A('C') is A.C:
    print(1)