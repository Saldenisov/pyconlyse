from abc import abstractmethod


class A:
    def __init__(self):
        self.a = 10
        # self.b = 2
        setattr(self, 'b', 2)



b = A()
print(b.b)