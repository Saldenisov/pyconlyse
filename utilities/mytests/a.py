from dataclasses import dataclass, asdict

@dataclass
class A:
    a: str = ''
    b: int = 2

a = A().__annotations__

b = A()
setattr(b, 'a', 'privet')
print(asdict(b))