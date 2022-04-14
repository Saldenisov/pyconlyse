import h5py
from h5py import Dataset, Group
import numpy as np

with h5py.File("test.hdf5", 'a') as h5f :
    # data = np.arange(0, 10)
    # data = data.reshape((1, 10))
    # # print(data)
    # dset = h5f.create_dataset("test4", (1, 10), maxshape=(None, 10), data=data)
    # dset = h5f.get('test5')
    # # dset.resize((dset.shape[0] + data.shape[0]), axis=0)
    # # dset[-data.shape[0]:] = data


    print(len(h5f['one'].shape))
    h5f.close()


# with h5py.File("E:\\data\\h5\\Data_pyconlyse_1.hdf5", 'a') as h5f:
#     p = {}
#     def fill_keys(d, obj):
#         if len(obj.keys()) == 0:
#             return None
#         else:
#             for key in obj.keys():
#                 if isinstance(obj[key], h5py.Dataset):
#                     d[key] = None
#                 else:
#                     d[key] = {}
#                     d[key] = fill_keys(d[key], obj[key])
#             return d
#
#     p = fill_keys(p, h5f)
#     print(f'd :{p}')
