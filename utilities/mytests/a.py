from datetime import datetime
from time import sleep


a = datetime.timestamp(datetime.now())
t = datetime.fromtimestamp(a).time()
print(t.strftime("%H:%M:%S"))