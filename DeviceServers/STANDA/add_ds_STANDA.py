
from tango import DbDevInfo, Database, AttributeInfo

db = Database()

names = {'00003D73': ['ELYSE/motorized_devices', 'StandaI_X', 'MM1_X', [-10, 0, 10], [-300, 300], 15731,
                      ['step', 1]],
         '00003D6A': ['ELYSE/motorized_devices', 'StandaI_Y', 'MM1_Y', [-10, 0, 10], [-300, 300], 15722,
                      ['step', 1]],
         '000043D6': ['ELYSE/motorized_devices', 'StandaII_X', 'MM2_X', [-10, 0, 10], [-300, 300], 17366,
                      ['step', 1]],
         '000043CF': ['ELYSE/motorized_devices', 'StandaII_Y', 'MM2_Y', [-10, 0, 10], [-300, 300], 17359,
                      ['step', 1]],
         '00003D98': ['manip/V0', 'StandaIII_X', 'MM3_X', [-10, 0, 10], [-300, 300], 15768,
                      ['step', 1]],
         '00003D8F': ['manip/V0', 'StandaIII_Y', 'MM3_Y', [-10, 0, 10], [-300, 300], 15759,
                      ['step', 1]],
         '000043F3': ['manip/V0', 'IrisExp_1', 'DV01', [0, 5, 10, 15, 25, 40, 100], [0, 100], 17395,
                      ["%", 20.61]],
         '000043D9': ['manip/V0', 'IrisExp_2', 'DV02', [0, 5, 10, 15, 25, 40, 100], [0, 100], 17369,
                      ["%", 21.85]],
         '00004A38': ['manip/V0', 'IrisExp_3', 'DV03', [0, 5, 10, 15, 25, 40, 100], [0, 100], 19000,
                      ["%", 22.46]],
         '00004A3E': ['manip/V0', 'IrisExp_4', 'DV04', [0, 5, 10, 15, 25, 40, 100], [0, 100], 19006,
                      ["%", 22.38]],
         '000043CA': ['manip/V0', 'ShutterExp_1', 'S1', [-1, 1], [-1.1, 1.1], 17354,
                      ['state', 1250]],
         '000043FE': ['manip/V0', 'ShutterExp_2', 'S2', [-1, 1], [-1.1, 1.1], 17406,
                      ['state', 1250]],
         '00004A15': ['manip/V0', 'ShutterOPA', 'S3', [-1, 1], [-1.1, 1.1], 18965,
                      ['state', 1250]],
         '00004A10': ['manip/V0', 'Flipper_1', 'F1', [-1, 1], [-1.1, 1.1], 18960,
                      ['state', 1250]],
         '00004399': ['manip/V0', 'Lambda_2_Exp', 'L-2_1', [0, 5, 10, 15, 20, 50, 100], [0, 100], 17305,
                      ["%", 37.00]],
         '00003B37': ['manip/V0', 'StandaIV_X', 'MM4_X', [-10, 0, 10], [-300, 300], 15159,
                      ['step', 1]],
         '00003B1B': ['manip/V0', 'StandaIV_Y', 'MM4_Y', [-10, 0, 10], [-300, 300], 15131,
                      ['step', 1]],
         '00004402': ['manip/V0', 'OPA_output_X', 'OPA_X', [-10, 0, 10], [-300, 300], 17410,
                      ['step', 1]],
         '000043D4': ['manip/V0', 'OPA_output_Y', 'OPA_Y', [-10, 0, 10], [-300, 300], 17364,
                      ['step', 1]],
         '000043E3': ['manip/V0', 'translation_stage_SC_mirror', 'TS_SC_m', [-3, 0, 3], [0, 15], 17379,
                      ['mm', 833.3333]],
         '000043DE': ['manip/V0', 'translation_stage_OPA_m', 'TS_OPA_m', [-10, 0, 10], [-100, 100], 2,
                      ['mm', 833.3333]],
         '000043F5': ['ELYSE/motorized_devices', 'IrisElyse_1', 'DE1', [0, 9.2, 15, 20, 25, 40, 100], [0, 100], 17397,
                      ["%", 21.59]],
         '000043FC': ['ELYSE/motorized_devices', 'IrisElyse_2', 'DE2', [0, 10, 15, 20, 25, 40, 100], [0, 100], 17404,
                      ["%", 22.32]],
         '00003B20': ['ELYSE/motorized_devices', 'ELYSE_X', 'MME_X', [-10, 0, 10], [-300, 300], 15136,
                      ['step', 1]],
         '00003B1C': ['ELYSE/motorized_devices', 'ELYSE_Y', 'MME_Y', [-10, 0, 10], [-300, 300], 15132,
                      ['step', 1]]}


def main():
    i = 1
    a = []
    for uri, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f'{val[0]}/{val[2]}'
        dev_info.name = dev_name
        dev_info._class = 'DS_Standa_Motor'
        dev_info.server = f'DS_Standa_Motor/{i}_{val[2]}'
        a.append(f'{i}_{val[2]}')
        db.add_device(dev_info)
        db.put_device_property(dev_name, {'ip_address': '10.20.30.204', 'uri': uri, 'friendly_name': val[1],
                                          'wait_time': 5, 'server_id': i, 'preset_pos': val[3], 'limit_min': val[4][0],
                                          'limit_max': val[4][1], 'real_pos': 0.0, 'device_id': val[5],
                                          'unit': val[6][0], 'conversion': val[6][1]})

        i += 1
    # print(a)
if __name__ == '__main__':
    main()
