import numpy as np

def correct_cursors_pos(cursors, rows, columns):
    """
    Correct cursors (pixels) so they do not become larger than data shape
    """
    if(cursors['x1'] < 0):
        cursors['x1'] = 0

    if(cursors['x1'] >= columns):
        cursors['x1'] = columns

    if(cursors['x2'] < 0):
        cursors['x2'] = 0

    if(cursors['x2'] >= columns):
        cursors['x2'] = columns

    if(cursors['y1'] < 0):
        cursors['y1'] = 0

    if(cursors['y1'] >= rows):
        cursors['y1'] = rows

    if(cursors['y2'] < 0):
        cursors['y2'] = 0

    if(cursors['y2'] >= rows):
        cursors['y2'] = rows

    return cursors


def search_closet_dict(search_value, diction, getMin):
    diff = float('inf')
    for key, value in diction.items():
        if diff > abs(search_value - value):
            diff = abs(search_value - value)
            x = key
    return x


def gaussian(x, A, sigma, x0):
    res = A / sigma / \
        np.sqrt(2 * np.pi) * \
        np.exp(-((x - x0) * (x - x0)) / (2 * sigma * sigma))
    return res


def exp(x, *args):
    tau = args
    res = np.exp(-(x / tau))
    return res


def stretch_exp(x, *args):
    tau, beta = args
    res = np.exp(-(x / tau)**beta)
    return res


def exp2(x, *args):
    a1, tau1, a2, tau2 = args
    res = a1 * np.exp(-(x / tau1)) + a2 * np.exp(-(x / tau2))
    return res
