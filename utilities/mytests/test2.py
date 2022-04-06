from pathlib import Path
import numpy as np

p = Path('D:\\DATA_VD2\\2021\\20211019-VC\\waves_long.txt')
d = np.loadtxt(str(p), dtype=float)
d_t = d[::2]


print(len(d))
np.savetxt('D:\\DATA_VD2\\2021\\20211019-VC\\waves_short.txt', d_t, fmt='%3.3f')
