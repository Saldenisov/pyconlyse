from operator import xor
from time import time

def solution(start, length):
    from operator import xor
    from time import time

    if length == 0:
        return start


    def findXOR(n):
        mod = n % 4
        if mod == 0:
            return n
        elif mod == 1:
            return 1
        elif mod == 2:
            return n + 1
        elif mod == 3:
            return 0

    def findXORFun(l, r):
        return xor(findXOR(l - 1), findXOR(r))

    checksum = 0
    for i in range(length):
        # print(start, start + length)
        res = findXORFun(start, start + length - 1)
        checksum ^= res
        start += length + i
        length -= 1
    return checksum



a = time()
print(solution(0, 2000000))
b = time()
print(b - a)



