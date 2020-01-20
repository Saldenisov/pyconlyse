from abc import  abstractmethod

class A:

    @abstractmethod
    def a(self):
        print(300)

class B(A):
    def a(self):
        super().a()
        print(200)


class C(B):
    def __init__(self):
        self._c = [1]*6

    def a(self):
        super().a()
        print(100)


c = C()
c._c[1] = [20]

print(c._c)