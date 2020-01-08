class A:
    F = None

    def s(self, F):
        A.F = F

    def p(self):
        print(A.F)


a = A()
a.s(2)
a.p()

a.s(str)
a.p()