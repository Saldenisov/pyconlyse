class A:
    def a(self):
        pass

    def c(self):
        pass

class B(A):
    pass


a = B()
print(hasattr(a, 'b'))