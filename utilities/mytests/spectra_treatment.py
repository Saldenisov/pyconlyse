from numpy import where, min, array
from scipy.spatial.distance import pdist
res = []
m = 0.1

def similiraty(data1, data2, diff=3, t=0, min_distance=-1):
    data = []
    for d1, d2 in zip(data1, data2):
        if t == 0:
            val = pdist([d1, d2])
        elif t == 1:
            val = pdist([d1, d2], 'cosine')
        data.append(val[0])
    data = array(data)
    m = min(data)
    if min_distance > 0:
        idx = where((data <= m * diff) & (data <= min_distance))
    else:
        idx = where(data <= m * diff)
    res = idx[0].tolist()
    return res, m