from scipy.cluster import hierarchy as hier
from numpy import min, where, array
def similiraty(data, diff=3):
    data = array(data)
    z = hier.linkage(data, method="single")
    min_distance = min(z[:, 2])
    clusters = hier.fcluster(z, t=min_distance * diff, criterion='distance')
    idx = where(clusters == 1)[0]
    return set(idx.tolist())