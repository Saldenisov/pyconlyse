#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys

from pathlib import Path
from typing import Union, Tuple
from datetime import datetime
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))
from tango import AttrWriteType, DispLevel, DevState
from threading import Thread
from time import sleep
from DeviceServers.General.DS_general import DS_General, standard_str_output
import h5py
import zlib
import msgpack
from abc import abstractmethod
from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property
from typing import Union, Tuple, Dict, Any

from DeviceServers.General.DS_general import DS_General, standard_str_output
from utilities.datastructures.mes_independent.measurments_dataclass import ArchiveData, Scalar, Array
import numpy as np

class DS_Archive(DS_General):

    _version_ = '0.1'
    _model_ = 'DS_Archiving'
    polling_local = 25
    maximum_size = device_property(dtype=int)
    folder_location = device_property(dtype=str)

    def init_device(self):
        self.file_h5: h5py.File = None
        self.file_working: Path = None
        self.lock = False
        self.close_thread = Thread(target=self.closing, args=[5])
        super().init_device()
        self.folder_location = Path(self.folder_location)
        if not self.folder_location.exists():
            self.folder_location.mkdir(parents=True, exist_ok=True)
        self.turn_on()
        self.close_thread.start()

    def closing(self, time):
        while True:
            sleep(5)
            if not self.lock:
                self.close_h5()
            else:
                while not self.lock:
                    sleep(0.01)
                self.close_h5()


    @command(dtype_in=str, dtype_out=str)
    def archive_it(self, data_string):
        try:
            self.lock = True
            self.open_h5()
            if not self.file_h5:
                return 'Cannot open h5 file.'
            else:
                data_bytes = eval(data_string)
                data = zlib.decompress(data_bytes)
                data: ArchiveData = msgpack.unpackb(data, strict_map_key=False)
                data_to_archive = None
                if isinstance(data.data, Scalar):
                    data_to_archive = np.array(data.data.value)
                elif isinstance(data.data, Array):
                    data_to_archive = np.frombuffer(data.data.value, dtype=np.dtype(data.data.dtype))
                    data_to_archive = data_to_archive.reshape(data.data.shape)

                if data_to_archive:
                    ts = float(data.data_timestamp)
                    dt = datetime.fromtimestamp(ts)
                    date_as_str = dt.date().__str__()
                    group_date = self.check_group(self.file_h5, date_as_str)
                    group_device = self.check_group(group_date, data.tango_device)
                    self.dataset_update(group_device, data.dataset_name, data.data.shape,
                                        maxshape=(None, data.data.shape[1]), dtype=np.dtype(data.data.dtype),
                                        data=data_to_archive)
                    self.dataset_update(group_device, f'{data.dataset_name}_timestamp', (1, 1), (None, 1), np.float, ts)
        except Exception as e:
            self.error(e)
        finally:
            self.lock = False

    def check_group(self, container: Union[h5py.File, h5py.Group], group_name):
        if group_name in container:
            group_date = container[group_name]
        else:
            group_date = container.create_group(name=group_name)
        return group_date

    def dataset_update(self, container: Union[h5py.File, h5py.Group], dataset_name, shape, maxshape, dtype, data):
        if dataset_name in container:
            ds = container[dataset_name]
            ds.resize((ds.shape[0] + data.shape[0]), axis=0)
            ds[-data.shape[0]:] = data
        else:
            container.create_dataset(name=dataset_name, shape=shape, maxshape=maxshape, dtype=dtype, data=data)

    def create_new_h5(self, latest=None):
        if latest:
            stem = latest.stem
            idx = int(stem.split('_')[-1])
            file = self.folder_location / f'Data_pyconlyse_{idx}.hdf5'
        else:
            file = self.folder_location / 'Data_pyconlyse_1.hdf5'
        self.info(f'Creating new file: {file}', True)
        self.file_working = file

    def open_h5(self):
        if not self.file_h5:
            file = str(self.file_working)
            self.info(f'Openning file: {file}', True)
            self.file_h5 = h5py.File(file, 'a')

    def close_h5(self):
        if self.file_h5:
            file = str(self.file_working)
            self.info(f'Closing file: {file}', True)
            self.file_h5.close()
            self.file_h5 = None

    def latest_h5(self):
        h5_files = list(self.folder_location.glob('*.hdf5'))
        if h5_files:
            latest = 0
            latest_idx = 0
            i = 0
            for file in h5_files:
                if latest < file.stat().st_ctime:
                    latest = file.stat().st_ctime
                    latest_idx = i
                i += 1
            file = h5_files[latest_idx]
            if file.stat().st_size < self.maximum_size:
                self.file_working = file
            else:
                self.create_new_h5(latest=file)
        else:
            self.create_new_h5()

    def find_device(self) -> Tuple[int, str]:
        arg_return = 1, 'qwerty'
        self.info(f"Searching for Archive device {self.device_name}", True)
        return arg_return

    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    def turn_on_local(self) -> Union[int, str]:
        self.latest_h5()
        self.open_h5()
        if self.file_h5:
            self.set_state(DevState.ON)
        else:
            self.set_state(DevState.FAULT)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self.close_h5()
        self.close_thread = None
        self.set_state(DevState.OFF)
        return 0


if __name__ == "__main__":
   DS_Archive.run_server()
