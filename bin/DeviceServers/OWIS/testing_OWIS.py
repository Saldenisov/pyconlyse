from tango import DeviceProxy
from time import sleep


# Get proxy on the tango_test1 device
print("Creating proxy to TangoTest device...")
DLs_VD2 = DeviceProxy("manip/VD2/DLs_VD2")

# ping it
print(DLs_VD2.ping())

# get the state
print(DLs_VD2.state())

print(DLs_VD2.get_attribute_list())
print(DLs_VD2.get_property('friendly_name')['friendly_name'][0])
print(DLs_VD2.uri)


n = 10
move = 10
for i in range(n):
    if i % 2 == 0:
        move = 2
    else:
        move = 0
    print(f'Moving: {i} to {move}mm.')
    DLs_VD2.position = move
    sleep(.5)
    print(f'Position is {DLs_VD2.position}.')
