from dataclasses import dataclass


@dataclass
class A:
    n: int
    data: str


@dataclass
class B(A):
    data: dict


a = A(1, '2')
b = B(1, {})
print(b)