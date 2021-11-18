class A:
    a = 0


a = A()
print(a.b)
setattr(a, 'b', 10)


print(a.a)
print(a.b)
