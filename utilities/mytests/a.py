from enum import Enum

class A( Enum):
    C = 'C'
    B = 'B'
    D= 'D'





if A.D in [A.C, A.B]:
    print(1)