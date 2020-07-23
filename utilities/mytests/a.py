from dataclasses import dataclass

@dataclass
class A:
    a: str = ''
    b: int = 2

a = A().__annotations__.keys()

b = A()
setattr(b, 'a', 'privet')
print(b.__get)