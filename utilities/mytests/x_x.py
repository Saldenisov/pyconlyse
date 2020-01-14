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

    @property
    def c(self):
        return self._c

    @c.setter
    def c(self, value):
        print('setting item of _c')
        self._c = value

c = C()
c.a()
c.c = [0]

print(c.c)