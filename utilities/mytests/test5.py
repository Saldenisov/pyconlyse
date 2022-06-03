from copy import deepcopy

class A:

    def __init__(self):
        self._b = {'q': -15}

    def b(self):
        return self._b

a = A()

c = {'c': a._b}


print(c['c'])
a._b['q'] = 15
print(c['c'])

