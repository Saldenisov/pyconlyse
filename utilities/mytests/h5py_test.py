import h5py
from h5py import Dataset, Group
import numpy as np

with h5py.File("dset.h5", 'a') as h5f :
    data = np.arange(10, 20)
    # data = data.reshape((1, 10))
    # # print(data)
    # dset = h5f.create_dataset("top/middle/bottom/test2", (10, ), maxshape=(None, ), data=data)
    dset = h5f.get("top/middle/bottom/test2")
    d = dset[:]
    indexes_lower = [idx[0] for idx in np.argwhere(d <= 16)]
    d = dset[indexes_lower]
    indexes_upper = [idx[0] for idx in np.argwhere(d >= 12)]
    d = d[indexes_upper]

    print(d)
    # # dset.resize((dset.shape[0] + data.shape[0]), axis=0)
    # # dset[-data.shape[0]:] = data


    # print(h5f['2022-04-15']['ELYSE']['motorized_devices']['DE1'].keys())
    # print(h5f['2022-04-15']['ELYSE']['motorized_devices']['DE1']['position'])
    # print(h5f['2022-04-15']['ELYSE']['motorized_devices']['DE1']['position_timestamp'])
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
