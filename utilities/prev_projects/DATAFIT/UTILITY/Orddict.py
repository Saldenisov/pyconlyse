'''
Created on 18 juil. 2016

@author: saldenisov
'''

from collections import OrderedDict


class Orddict(OrderedDict):
    """
    Orddict is extented OrderedDict from collections
    It allows to get last_key

    >>> d = Orddict()
    >>> d['b'] = 1
    >>> d['a'] = 2
    >>> d.last
    'a'
    >>> d['c'] = 2
    >>> d.last
    'c'
    """
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.__last_key = None

    def __setitem__(self, *args, **kwds):
        super().__setitem__(*args, **kwds)
        self.__last_key = args[0]

    def __delitem__(self, *args, **kwds):
        super().__delitem__(*args, **kwds)
        self.__last_key = self.last

    @property
    def last(self):
        key=next(reversed(self))
        return key

#===============================================================================
# if __name__ == "__main__":
#     import doctest
#     doctest.testmod()
#===============================================================================
