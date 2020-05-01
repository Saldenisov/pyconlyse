import dis
from time import time_ns

def func_a():
    dict_a = {}
    i = 10
    c  = 2
    while i < 100000:
        if dict_a or i == 100:
            c = 10
            print(c)
        i += 1
    return 'return'





# Show how the functions execute
print('Case 1')
def test(n):
    for i in range(n):
        b = time_ns()
        func_a()
        e = time_ns()
        print(i, f'{(e - b) / 10 ** 9}')
test(100)
#dis.dis(func_a)

