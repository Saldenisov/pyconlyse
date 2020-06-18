from dataclasses import dataclass, field

@dataclass
class A():
    a: dict = field(default_factory=lambda: {1:1})

b = A()
print(b)