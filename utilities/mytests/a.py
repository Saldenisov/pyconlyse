class A:
    pass

class B(A):
    pass

print(type(B()).__bases__)