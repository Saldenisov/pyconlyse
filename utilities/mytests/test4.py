% pwd
% matplotlib
inline
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import nibabel as nib
from scipy.spatial.distance import pdist
from scipy.cluster import hierarchy as hier
from pathlib import Path
from zipfile import ZipFile
from glob import glob
from dataclasses import dataclass
import h5py as h5
import itertools
from multiprocessing import Pool
import time
import gzip

default_dir = Path("C:/Users/denisov/ownCloud/LCP/Projects")


@dataclass
class DataRaw:
    wavelengths: np.ndarray
    timedelays: np.ndarray
    data: np.ndarray
    file_name: str
    comments: dict

    def calc_od(self):
        BG1 = np.concatenate(self.data[:, 0])
        Ir1 = np.concatenate(self.data[:, 1])
        Is1 = np.concatenate(self.data[:, 2])
        BG2 = np.concatenate(self.data[:, 3])
        Ir2 = np.concatenate(self.data[:, 4])
        Is2 = np.concatenate(self.data[:, 5])
        OD = None
        number = 0
        for bg1, bg2, ir1, ir2, is1, is2 in zip(BG1, BG2, Ir1, Ir2, Is1, Is2):
            number += len(bg1)
            bg1 = np.average(bg1, axis=0)
            bg2 = np.average(bg2, axis=0)
            ir1 = np.average(ir1, axis=0)
            ir2 = np.average(ir2, axis=0)
            is1 = np.average(is1, axis=0)
            is2 = np.average(is2, axis=0)
            try:
                dem1 = is2 - bg2
                dem2 = ir2 - bg2
                dem1[dem1 == 0] = 0.001
                dem2[dem2 == 0] = 0.001
                bot = (ir1 - bg1) / dem2
                bot[bot == 0] = 0.001
                res = np.abs(((is1 - bg1) / dem1) / bot)
                res[res == 0] = 0.0001
                od = np.log10(res)
            except Exception:
                raise

            if not isinstance(OD, np.ndarray):
                OD = od
            else:
                OD = np.vstack([OD, od])

            self.od = OD



@dataclass
class Data:
    wavelengths: np.ndarray
    timedelays: np.ndarray
    data2D: np.ndarray
    file_name: str


def arrange_data_h5(path: Path):
    h5_file = h5.File(str(path), 'a')
    timedelays = h5_file['timedelays'][:]
    wavelengths = h5_file['wavelengths'][:]
    data = h5_file['raw_data'][:]
    h5_file.close()
    return DataRaw(wavelengths, timedelays, data, path.stem, {})

def calc_od(data_raw: DataRaw, sim, diff=10):


