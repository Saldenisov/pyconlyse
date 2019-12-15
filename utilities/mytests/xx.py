class A():
    def a(self):
        print(self.__class__.__name__)

class B(A):
    def a(self):
        super().a()
        print(self.__class__.__name__)

class C(B):

    def a(self):
        super().a()
        print(self.__class__.__name__)

c = C()
c.a()