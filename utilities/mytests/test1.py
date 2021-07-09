class A:
    def __init__(self):
        self.a = 10

    def b(self):

        def c():
            self.a = 20
        c()

a = A()
a.b()
print(a.a)