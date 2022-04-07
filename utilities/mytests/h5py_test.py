import h5py
import numpy as np
# Create some data
data1 = np.arange(100.)
data2 = 2.0*data1
data3 = 3.0*data1
data4 = 3.0*data1

# use namesList to define dtype for recarray
namesList = ['height', 'mass', 'velocity', 'gravity']
ds_dt = np.dtype({'names': namesList,'formats': [(float)]*4 })

rec_arr = np.rec.fromarrays([data1, data2, data3, data4], dtype=ds_dt)

names = ['data', 'time']
ds_dt = np.dtype({'names': names, 'formats': [(int)] * 2 })

DATA = np.random.rand(5, 3)
timestamps = np.arange(0, 3)

rec_arr = np.rec.fromarrays([DATA, timestamps], dtype=ds_dt)
with h5py.File("experimentReadings.hdf5", 'a') as h5f :

    dset = h5f.create_dataset("strange", (3, 5, 3), data=rec_arr)
    keys = h5f.keys()
    dset = h5f.get('strange')
    height = dset[:,'data']
    print(height)
    print(dset)
    h5f.close()