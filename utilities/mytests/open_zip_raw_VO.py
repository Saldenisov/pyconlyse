from pathlib import Path
from zipfile import ZipFile
import numpy as np


p = Path('C:\\dev\\2_DEG-N2O-5-47 PM.zip')
p_raw = f'{p.stem}.raw'
print(f'Trying to read zipped Raw file for V0: {p}')

with ZipFile(p, 'r') as zip:
    with zip.open(p_raw, 'r') as raw_file:
        lines = raw_file.readlines()
        # Setting waves
        try:
            waves = np.fromstring(lines[0].decode('utf-8'), sep='\t')
        except Exception as e:
            print(f'Waves cannot be set {e}.')
        print(f'Waves: {waves}')
        # Setting data and timedelays
        timedelays = []
        data = []
        data_loc = []
        started_point = False
        for line in lines:
            line = line.decode('utf-8')
            if not started_point:
                if 'S_' in line:
                    started_point = True
                    timedelay = float(line[2:])
                    timedelays.append(timedelay)
                    data_loc = []
            else:
                if len(line) < 6:
                    if 'E_' in line:
                        started_point = False
                        data.append(data_loc)
                else:
                    try:
                        data_loc.append(np.fromstring(line, sep='\t'))
                    except Exception as e:
                        print(f'Data line cannot be installed: {e}, timedelay: {timedelay}')
                        raise e


        if not data:
            raise Exception('No data were set.')
        else:
            timedelays = np.array(timedelays)
            data = np.array(data)
            print(f'Timedelays: {timedelays}')
            print(f'Data[0]: {data[0]}')