import pandas as pd
import numpy as np
import io
from pathlib import Path
from zipfile import ZipFile
from glob import glob
from dataclasses import dataclass


@dataclass
class DataRaw:
    wavelengths: np.ndarray
    timedelays: np.ndarray
    data: np.ndarray
    file_name: str

def arrange_data(path: Path):
    timedelays = []
    data_3D = []
    with ZipFile(path) as myzip:
        with myzip.open(path.stem + ".raw") as myfile:
            data_raw = io.TextIOWrapper(myfile)
            waves_str = data_raw.readline()
            wavelengths = np.fromstring(waves_str, dtype=float, sep='\t')
            # read another line
            line = data_raw.readline()
            data_2D = []
            print(f'{path.stem}')
            while line != '':
                if "S_" in line:
                    timedelay = float(line[2:])
                elif "E_" in line:
                    np2d = np.array(data_2D)
                    data_3D.append(np2d)
                    data_2D = []
                    timedelays.append(timedelay)
                elif len(line) > 10:
                    data_2D.append(np.fromstring(line, dtype=float, sep='\t'))
                line = data_raw.readline()


    data_3D = np.array(data_3D)
    data_3D_sorted = []
    for data_td in data_3D:
        BG = []
        Ie = []
        Io = []
        data_td_sorted = []
        for measurement_td in np.split(data_td, len(data_td) / 6):
            BG.append(measurement_td[0])
            BG.append(measurement_td[1])
            Ie.append(measurement_td[2])
            Ie.append(measurement_td[3])
            Io.append(measurement_td[4])
            Io.append(measurement_td[5])
        data_td_sorted.append(BG)
        data_td_sorted.append(Ie)
        data_td_sorted.append(Io)
        data_3D_sorted.append(data_td_sorted)

    data_3D_sorted = np.array(data_3D_sorted)
    timedelays = np.array(timedelays)

    return DataRaw(wavelengths, timedelays, data_3D_sorted, path.stem)

dir_path = Path("C:\dev\DATA")

files_zip = [Path(file) for file in glob(str(dir_path / '*.zip'))]

files_df = [arrange_data(path) for path in files_zip]