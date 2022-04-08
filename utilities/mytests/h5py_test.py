import h5py
import numpy as np

with h5py.File("test.hdf5", 'a') as h5f :
    dset = h5f.create_dataset("test1", (2,), maxshape=(None, ), data=[1, 2])
    dset =h5f.get('one_r')
    data = np.zeros(10)
    dset.resize((dset.shape[0] + data.shape[0]), axis=0)
    dset[-data.shape[0]:] = data
    print(dset)
    h5f.close()