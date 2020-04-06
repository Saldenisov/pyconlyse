import numpy as np


a = np.ones(shape=(3,3))
print(a)

b = np.ones(shape=(3))*100
c = np.ones(shape=(3))*200
c = np.insert(c, 0, 0)
print(f'b={b}')
print(f'c={c}')


d = np.vstack((b,a))
d = np.transpose(d)
d = np.vstack((c, d))
print(f'd ={d}')

