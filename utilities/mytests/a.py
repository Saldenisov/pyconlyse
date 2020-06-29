from enum import Enum

class A(Enum):
    b = 'basd'
    c = 'casdsad'

    def __repr__(self):
        return str(self)

print(A.b.__repr__())