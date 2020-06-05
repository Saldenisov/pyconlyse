import numpy as np
from pathlib import Path


p = Path('C:\Dev\DATA\M1043.dat')

a = np.loadtxt(p)

l = a[0][1:]

c = a[:,0][1:]

d = 0