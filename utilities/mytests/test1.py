from threading import Thread


def a():
    from time import sleep
    i = 0
    while True:
        i += 1
        print(i)
        sleep(0.1)

d = {}

thr = Thread(target=a)

d[1] = thr
thr.start()
del d[1]
print(d)