
from datetime import datetime

# current date and time
now = datetime.now()

timestamp = datetime.timestamp(now)
print(type(timestamp))

print("timestamp =", timestamp)

print(datetime.fromtimestamp(timestamp))