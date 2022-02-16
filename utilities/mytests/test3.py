#
# This examaple creates an HDF5 file dset.h5 and an empty datasets /dset in it.
#
import h5py
#
# Create a new file using defaut properties.
#
file = h5py.File('dset.h5','w')
#
# Create a dataset under the Root group.
#
dataset = file.create_dataset("dset",(4, 6), h5py.h5t.STD_I32BE)
print("Dataset dataspace is", dataset.shape)
print("Dataset Numpy datatype is", dataset.dtype)
print("Dataset name is", dataset.name)
print("Dataset is a member of the group", dataset.parent)
print("Dataset was created in the file", dataset.file)
#
# Close the file before exiting
#
file.close()



#
# This examaple creates and writes two attributes on the "dset" dataset created by h5_crtdat.py.
#
import h5py
import numpy as np
#
# Open an existing file using defaut properties.
#
file = h5py.File('dset.h5','r+')
#
# Open "dset" dataset.
#
dataset = file['/dset']
#
# Create string attribute.
#
attr_string = "Meter per second"
dataset.attrs["Units"] = attr_string
#
# Create integer array attribute.
#
attr_data = np.zeros((2))
attr_data[0] = 100
attr_data[1] = 200
#
#
dataset.attrs.create("Speed", attr_data, (2,), h5py.h5t.STD_I32BE)
#
# Close the file before exiting
#
file.close()


#
# This example writes data to the existing empty dataset created by h5_crtdat.py and then reads it back.
#
import h5py
import numpy as np
#
# Open an existing file using defaut properties.
#
file = h5py.File('group.h5','r+')
#
# Open "MyGroup" group and create dataset dset1 in it.
#
print("Creating dataset dset1 in MyGroup group...")
dataset1 = file.create_dataset("/MyGroup/dset1", (3,3), dtype = h5py.h5t.STD_I32BE)
#
# Initialize data and write it to dset1.
#
data = np.zeros((3,3))
for i in range(3):
    for j in range(3):
        data[i][j] = j + 1
print("Writing data to dset1...")
dataset1[...] = data

#
# Open "MyGroup/Group_A" group and create dataset dset2 in it.
#
print("Creating dataset dset2 in /MyGroup/Group_A group...")
group = file['/MyGroup/Group_A']
dataset2 = group.create_dataset("dset2", (2,10), dtype = h5py.h5t.STD_I16LE)
#
# Initialize data and write it to dset2.
#
data = np.zeros((2,10))
for i in range(2):
    for j in range(10):
        data[i][j] = j + 1
print("Writing data to dset2...")
dataset2[...] = data
#
# Close the file before exiting.
#
file.close()
