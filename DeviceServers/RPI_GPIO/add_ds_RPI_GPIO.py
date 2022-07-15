from tango import DbDevInfo, Database

db = Database()


names = {1: ['manip/V0', 'RPI4_GPIO_Controller', 'RPI4_GPIO_V0', '129.175.100.171', 'rpi4_1',
             {'Pins': [(4, 'LED', 'Laser_shutter', 0, 'gpiozero'), (3, 'LED', 'Room_light', 0, 'gpiozero'),
                       (17, 'LED', 'step_A4988_4st', 0, 'zmq'), (27, 'LED', 'step_A4988_5th', 0, 'zmq'),
                       (22, 'LED', 'PUL+_DM542_3rd', 0, 'zmq'), (23, 'LED', 'PUL+_DM542_2nd', 0, 'zmq'),
                       (18, 'LED', 'step_A4988_1st', 0, 'zmq'), (25, 'LED', 'step_A4988_2nd', 0, 'zmq'),
                       (5, 'LED', 'step_A4988_3rd', 0, 'zmq'), (6, 'LED', 'PUL+_DM542_1st', 0, 'zmq')
                       ]}
            ],
         2: ['manip/V0', 'RPI3_GPIO_Controller', 'RPI3_GPIO_Controller', '10.20.30.205', 'rpi3sc',
             {'Pins': [(17, 'LED', 'step_A4988_4st', 0), (27, 'LED', 'step_A4988_5th', 0),
                       (22, 'LED', 'PUL+_DM542_3rd', 0), (23, 'LED', 'PUL+_DM542_2nd', 0),
                       (18, 'LED', 'step_A4988_1st', 0), (25, 'LED', 'step_A4988_2nd', 0),
                       (5, 'LED', 'step_A4988_3rd', 0), (6, 'LED', 'PUL+_DM542_1st', 0)]}
             ]
         }

def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_RPI_GPIO'
        dev_info.server = f'DS_RPI_GPIO/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'ip_address': val[3], 'device_id': dev_id, 'friendly_name': val[1],
                                          'server_id': i, 'serial_number': val[4], 'parameters': str(val[5]),
                                          'number_pins': len(val[5]['Pins'])})
        i += 1


if __name__ == '__main__':
    main()
