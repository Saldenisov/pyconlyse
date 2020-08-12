from dataclasses import dataclass, asdict

@dataclass
class B:
    f1: str = 'f1'

@dataclass
class A(B):
    a: str = ''
    b: int = 2

a = A().__dataclass_fields__

b = A()
setattr(b, 'a', 'privet')
print(a)