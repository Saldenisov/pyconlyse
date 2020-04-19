from enum import Enum, Flag, auto

class D(Enum):
    FILES = str
    PORJECTS = 2

class Flags(Flag):
    Files = auto()
    PORJECTS = auto()


print(D.FILES == D.PORJECTS)


print(D.FILES.value)