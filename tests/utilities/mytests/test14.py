class B:
    def f(self):
        print(self.name)


from functools import partial

class A:

    def __init__(self, name):
        self.name = name
        self.a = partial(B.f, self)

    def a(self):
        pass




b = A('a')
b.a()