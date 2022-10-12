import numpy as np
# s = np.random.poisson(50, 10000)
s = np.random.normal(0.9580488725720484, 0.19, 1000)
# s = s = np.random.weibull(.1, 1000)
import matplotlib.pyplot as plt
a, b  = np.histogram(s, bins=100, density=True)
count, bins, ignored = plt.hist(s, 100, density=True)
plt.show()