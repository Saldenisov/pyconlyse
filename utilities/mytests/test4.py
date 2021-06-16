
import random

random.seed()
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from collections import namedtuple
from typing import Union, List
from scipy.optimize import least_squares

dt = 0.1
tb = 0
te = 1000
N = int((te - tb) / dt) +1
time_range = np.linspace(tb, te, N)
ct = np.zeros(N)

lifetime = 1/43

i = 0
for t in time_range:
    if t % 24 == 0:
        ct[i] = ct[i] + 10 / 1000 / 5 / 324
    ct[i + 1] = ct[i] - lifetime * dt * ct[i]
    i += 1


    if i == N - 1:
        break

time_range = np.array(time_range)
concentration = np.array(ct)

fig1, ax1 = plt.subplots()
ax1.plot(time_range, ct, 'b')
ax1.set_xlabel('Time, hours')
ax1.set_ylabel('Concentration, M')
ax1.set_title('Pharma kinetics')
ax1.grid(True)

plt.show()
