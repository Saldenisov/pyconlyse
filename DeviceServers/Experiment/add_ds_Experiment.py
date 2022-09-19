from tango import DbDevInfo, Database
from collections import OrderedDict as od
db = Database()


names = {'Pump-Probe': ['manip/CR', 'Stroboscopic pulse-probe', 'pulse-probe',  1,
                        {'available_detection': {'ANDOR_CCD': 'manip/cr/andor_ccd1'},
                         'translation_stages': {'samples': 'manip/general/ds_owis_ps90/2',
                                                'SC_delay': 'manip/general/ds_owis_ps90/1'},
                         'available_cell_holders': {'5mm': {'1': 0, '2': 12.9, '3': 25.8, '4': 38.7, '5': 51.6,
                                                            '6': 64.5, 'lanex': 80}, '10mm': {'1':0, '2': 18, '3': 36,
                                                                                              'lanex': 105}},
                         'detection_settings': {'BG': 50000, 'pulse_difference': 10}}],
         '3P': ['manip/CR', 'Stroboscopic 3P experiment', 'pulse-repump-probe',  2,
                        {}],
         'Streak-camera': ['manip/CR', 'Streak-camera pulse-probe', 'pulse-probe-streak',  3,
                        {}]
         }


def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_Experiment'
        dev_info.server = f'DS_Experiment/{i}_{val[2]}'
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'device_id': dev_id, 'friendly_name': val[1], 'server_id': i,
                                          'serial_number': val[3], 'parameters': str(val[4])})
        i += 1


if __name__ == '__main__':
    main()
