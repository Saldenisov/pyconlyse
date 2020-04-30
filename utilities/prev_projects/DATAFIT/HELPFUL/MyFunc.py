'''
Created on 7 juin 2016

@author: saldenisov
'''
import numpy as np


def ndarray_tostring(arr):
    '''
    Convert ndarray to tab separated string

    >>> import numpy as np
    >>> a = np.array([1, 2, 3])
    >>> b = ndarray_tostring(a)
    >>> print(b)
    1.000
    2.000
    3.000
    >>> c = np.array([[1, 2, 3],[1, 2, 3]])
    >>> d = ndarray_tostring(c)
    >>> print(repr(d))
    '1.000\\t2.000\\t3.000\\n1.000\\t2.000\\t3.000'
    >>> e = np.array([[1, 2, None],[1, None, 3]])
    >>> f = ndarray_tostring(e)
    >>> print(repr(f))
    '1.000\\t2.000\\t--\\n1.000\\t--\\t3.000'
    '''
    s = ''
    size = len(np.shape(arr))

    if size == 1:
        for i in arr:
            if i == None or np.isnan(i):
                s += '--'
            else:
                s += format(i, '.3f')
            s += '\n'
        s = s[:-1]

    if size == 2:
        for i in arr:
            for j in i:
                if j == None or np.isnan(j):
                    s += '--'
                else:
                    s += format(j, '.3f')
                s += '\t'
            s = s[:-1]
            s += '\n'
        s = s[:-1]

    if size > 2:
        s = 'wrong numpy.ndarray size in ndarray_tostring'

    return s


def tuple_tostring(tuple_arr):
    """
    Takes tuple of arrays and convert them to string
    """
    pass


def dict_of_dict_to_array(dic):
    arr = []
    for key in dic:
        if not isinstance(dic[key], dict):
            arr.append(dic[key])
        else:
            arr.extend(dict_of_dict_to_array(dic[key]))
    return arr


if __name__ == "__main__":
    import doctest
    doctest.testmod()
