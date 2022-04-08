import numpy as np


a = 3
b = 4
c = 5

d = np.arange(0, a * b * c)
d = d.reshape((a, b, c))
print(d)


a = 1
b = 4
c = 5

d = np.arange(0, a * b * c)
d = d.reshape((a, b, c))
print(d)


