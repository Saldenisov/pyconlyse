class A:
    pass

class B(A, metaclass=None):
    pass


b = B()