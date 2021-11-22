from threading import Thread
from time import sleep

f = {}

def a(t,c,f, r):
    i = 0
    while i< 5:
        print(c)
        sleep(t)
        i += 1
    del f[r]

z = Thread(target=a, args=(.1,'Slava', f, 1))

f[1] = z
f[1].start()

sleep(1)
print(f)

