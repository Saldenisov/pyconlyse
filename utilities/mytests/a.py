import socket
import time

a = socket.create_connection(address=('10.20.30.131', '5025'))

a.send(b'*rst\n')
time.sleep(0.05)
a.send(b'*rcl 9\n')
time.sleep(0.1)
a.send(b'burm 1\n')
time.sleep(1)
a.send(b'burm 0\n')

print(a)