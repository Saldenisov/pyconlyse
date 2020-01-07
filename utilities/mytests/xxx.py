import inspect as ins

class A:

    def b(self, a, b):
        print(f'{a}  {b}')

    def c(self):
        method_list = [func for func in dir(A) if callable(getattr(A, func))]
        print(method_list)

    def d(self, com='b', parameters={}):
        f = getattr(self, com)
        if parameters.keys() == ins.signature(f).parameters.keys():
            f(**parameters)
        else:
            print('error')


a = A()
a.d(parameters={'b':1000, 'a': 232234, 'k':234})
