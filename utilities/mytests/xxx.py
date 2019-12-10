from time import sleep
from threading import Timer

def a(b):
    print(b)



if __name__ == '__main__':
    i = 0
    timer = Timer(3, a, ['kot'])
    timer.start()

    while i < 10:
        sleep(0.5)
        print(i)
        i += 1

    sleep(10)