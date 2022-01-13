
from tango import DbDevInfo, Database, AttributeInfo

db = Database()

names = {'test_device_id': ['ELYSE/test_devices', 'Test1', 'T1', 'First test device', '123456789']}


def main():
    i = 1
    for uri, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_Test'
        dev_info.server = f'DS_Test/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'uri': uri, 'friendly_name': val[3], 'device_id': val[4], 'unit': 'mm'})

        i += 1

if __name__ == '__main__':
    main()
