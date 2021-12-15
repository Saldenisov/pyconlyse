
from tango import DbDevInfo, Database

db = Database()

names = {'00003D73': ['ELYSE/motorized_devices', 'StandaI_X', 'MM1_X', [-10, 0, 10], [-300, 300], 15731],
         '00003D6A': ['ELYSE/motorized_devices', 'StandaI_Y', 'MM1_Y', [-10, 0, 10], [-300, 300], 15722],
         '000043D6': ['ELYSE/motorized_devices', 'StandaII_X', 'MM2_X', [-10, 0, 10], [-300, 300], 17366],
         '000043CF': ['ELYSE/motorized_devices', 'StandaII_Y', 'MM2_Y', [-10, 0, 10], [-300, 300], 17359],
         '00003D98': ['manip/V0', 'StandaIII_X', 'MM3_X', [-10, 0, 10], [-300, 300], 15768],
         '00003D8F': ['manip/V0', 'StandaIII_Y', 'MM3_Y', [-10, 0, 10], [-300, 300], 15759],
         '000043F3': ['manip/V0', 'IrisExp_1', 'DV01', [0, 200, 350, 650, 850, 1500], [0, 1500], 17395],
         '000043D9': ['manip/V0', 'IrisExp_2', 'DV02', [0, 200, 350, 650, 850, 1500], [0, 1500], 17369],
         '00004A38': ['manip/V0', 'IrisExp_3', 'DV03', [0, 200, 350, 650, 850, 1500], [0, 1500], 19000],
         '00004A3E': ['manip/V0', 'IrisExp_4', 'DV04', [0, 200, 350, 650, 850, 1500], [0, 1500], 19006],
         '000043CA': ['manip/V0', 'ShutterExp_1', 'S1', [-1250, 1250], [-1350, 1350], 17354],
         '000043FE': ['manip/V0', 'ShutterExp_2', 'S2', [-1250, 1250], [-1350, 1350], 17406],
         '00004A15': ['manip/V0', 'ShutterOPA', 'S3', [-1250, 1250], [-1350, 1350], 18965],
         '00004A10': ['manip/V0', 'Flipper_1', 'F1', [-1250, 1250], [-1350, 1350], 18960],
         '00004399': ['manip/V0', 'Lambda_2_Exp', 'L-2_1', [-100, -50, -10, 0, 10, 50, 100], [-4500, 4500], 17305],
         '00003B37': ['manip/V0', 'StandaIV_X', 'MM4_X', [-10, 0, 10], [-300, 300], 15159],
         '00003B1B': ['manip/V0', 'StandaIV_Y', 'MM4_Y', [-10, 0, 10], [-300, 300], 15131],
         '00004402': ['manip/V0', 'OPA_output_X', 'OPA_X', [-10, 0, 10], [-300, 300], 17410],
         '000043D4': ['manip/V0', 'OPA_output_Y', 'OPA_Y', [-10, 0, 10], [-300, 300], 17364],
         '000043E3': ['manip/V0', 'translation_stage_1', 'TS_1', [-10, 0, 10], [-100, 100], 1],
         '000043DE': ['manip/V0', 'translation_stage_2', 'TS_2', [-10, 0, 10], [-100, 100], 2],
         '000043F5': ['ELYSE/motorized_devices', 'IrisElyse_1', 'DE1', [0, 200, 350, 650, 850, 1500], [0, 1500], 17397],
         '000043FC': ['ELYSE/motorized_devices', 'IrisElyse_2', 'DE2', [0, 200, 350, 650, 850, 1500], [0, 1500], 17404],
         '00003B20': ['ELYSE/motorized_devices', 'ELYSE_X', 'MME_X', [-10, 0, 10], [-300, 300], 15136],
         '00003B1C': ['ELYSE/motorized_devices', 'ELYSE_Y', 'MME_Y', [-10, 0, 10], [-300, 300], 15132]}


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
                                          'limit_max': val[4][1], 'real_pos': 0.0, 'device_id': val[5]})

        i += 1

if __name__ == '__main__':
    main()
