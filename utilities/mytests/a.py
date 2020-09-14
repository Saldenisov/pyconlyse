from datetime import datetime
from time import sleep


a = datetime.timestamp(datetime.now())
sleep(1)
b = datetime.timestamp(datetime.now())


print(a-b)