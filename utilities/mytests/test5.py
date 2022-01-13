def partial(func, *args, **keywords):
    def newfunc(*fargs, **fkeywords):
        newkeywords = keywords.copy()
        newkeywords.update(fkeywords)
        return func(*args, *fargs, **newkeywords)
    return newfunc



def a(*args, x = 2, y = 3):
    result = 0
    for i in args:
        result += i
    return result ** x - y

b = partial(a, -1, 1, x = 2)

print(b(1,0, y=10))


