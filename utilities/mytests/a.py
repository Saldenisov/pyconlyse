def a():
    return 1


def b():
    a()
    a()
    print(2)

b()