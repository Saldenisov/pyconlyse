import getpass
import telnetlib
from time import sleep
HOST = "10.20.30.204"
user = 'admin'
password = 'elyse'

tn = telnetlib.Telnet(HOST, port=23)
tn.open(HOST, port=23)
user = user.encode('ascii') + b"\n"
tn.read_until(b"User Name: ")
tn.write(user)
password = password.encode('ascii') + b"\n"
tn.read_until(b"Password: ")
# tn.write(password.encode('ascii') + b"\n")
tn.write(password)
sleep(1)


print(tn.read_very_eager().decode('ascii'))

cmd1 = 'gpio clear 0'.encode('ascii') + b"\n"
tn.write(cmd1)
sleep(1)

cmd2 = 'gpio read 0'.encode('ascii') + b"\n"
tn.write(cmd2)
sleep(1)

print(tn.read_very_eager().decode('ascii'))

