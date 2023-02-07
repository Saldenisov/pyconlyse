from numpy import where, min, array
from scipy.spatial.distance import pdist
res = []
m = 0.1

def similiraty(data1, data2, diff=3):
    data = []
    for d1, d2 in zip(data1, data2):
        val = pdist([d1, d2], 'cosine')
        data.append(val[0])
    data = array(data)
    m = min(data)
    idx = where(data <= m * diff)
    res = idx[0].tolist()
    return res


def similiraty_min(data1, data2):
    data = []
    for d1, d2 in zip(data1, data2):
        val = pdist([d1, d2], 'cosine')
        data.append(val[0])
    data = array(data)
    m = min(data)
    return m


def test(data1, data2, diff=3):
    data = []
    for d1, d2 in zip(data1, data2):
        val = pdist([d1, d2], 'cosine')
        data.append(val[0])
    data = array(data)
    m = min(data)
    idx = where(data <= m * diff)
    res = idx[0].tolist()
    return res, m