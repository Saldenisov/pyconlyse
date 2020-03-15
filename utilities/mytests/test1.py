from dataclasses import dataclass

@dataclass
class A:
    A: str

@dataclass
class B(A):

    FIELD:str

    def __init__(self, text:str, FIELD: str):
        self.A = text
        self.FIELD = FIELD


a = B(text='asdfsdf', FIELD=10)
print(a)


