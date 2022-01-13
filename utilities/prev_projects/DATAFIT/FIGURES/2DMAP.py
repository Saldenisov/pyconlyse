'''
Created on 20 avr. 2015

@author: saldenisov
'''

import matplotlib.pyplot as plt
import numpy as np
import scipy.interpolate

# Generate datastructures:
x, y, z = 10 * np.random.random((3, 10))

# Set up a regular grid of interpolation points
xi, yi = np.linspace(x.getMin(), x.getMax(), 100), np.linspace(
    y.getMin(), y.getMax(), 100)
xi, yi = np.meshgrid(xi, yi)

# Interpolate
rbf = scipy.interpolate.Rbf(x, y, z, function='linear')
zi = rbf(xi, yi)

plt.imshow(zi, vmin=z.getMin(), vmax=z.getMax(), origin='lower',
           extent=[x.getMin(), x.getMax(), y.getMin(), y.getMax()])
plt.scatter(x, y, c=z)
plt.colorbar()
plt.show()


class do_Fit(object):
    '''
    classdocs
    '''

    def __init__(self, params):
        '''
        Constructor
        '''
