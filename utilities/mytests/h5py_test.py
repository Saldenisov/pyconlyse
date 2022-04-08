import h5py
import numpy as np

with h5py.File("test.hdf5", 'a') as h5f :
    data = np.arange(0, 10)
    data = data.reshape((1, 10))
    # print(data)
    dset = h5f.create_dataset("test4", (1, 10), maxshape=(None, 10), data=data)
    dset = h5f.get('test5')
    # dset.resize((dset.shape[0] + data.shape[0]), axis=0)
    # dset[-data.shape[0]:] = data
    a = np.array(dset)
    print(a)
    h5f.close()