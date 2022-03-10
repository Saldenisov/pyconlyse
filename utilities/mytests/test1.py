import h5py
import numpy as np

file_name = 'E:\\test.hdf5'

f = h5py.File(file_name, 'a')

# data = np.array([np.arange(1024)])
#
# dset = f.create_dataset("data1", data=data, dtype='uint16', maxshape=(None, 1024))

dset = f['data1']

print(dset.shape)


for i in range(24 * 3600 * 3):
    row_count = dset.shape[0]
    data = np.random.randint(0, 2 ** 16, 1024)

    dset.resize(row_count + 1, axis=0)

    # Write the next chunk
    dset[row_count:] = data


print(dset.shape)
