from tango import DeviceProxy
from time import sleep


# Get proxy on the tango_test1 device
print("Creating proxy to TangoTest device...")
ds_standa = DeviceProxy('ELYSE/motorized_devices/MM1_X')

# ping it
print(ds_standa.ping())

# get the state
print(ds_standa.state())

print(ds_standa.get_attribute_list())
print(ds_standa.get_property('friendly_name')['friendly_name'][0])
print(ds_standa.uri)


n = 10
move = 10
for i in range(n):
    if i % 2 == 0:
        move = 2
    else:
        move = 0
    print(f'Moving: {i} to {move}mm.')
    ds_standa.position = move
    sleep(.5)
    print(f'Position is {ds_standa.position}.')
