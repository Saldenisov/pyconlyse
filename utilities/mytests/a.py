from json import dumps
import numpy

arr = numpy.zeros(shape=(10,10)).tolist()
a = {1: arr}


b = dumps(a)
print(b)