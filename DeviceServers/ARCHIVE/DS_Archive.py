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
from numpy import array
uint8 = np.dtype('uint8')
int16 = np.dtype('int16')


DEV = False


class DS_Archive(DS_General):
    RULES = {'archive_it': [DevState.ON], **DS_General.RULES}

    _version_ = '0.1'
    _model_ = 'DS_Archiving'
    polling_local = 25
    maximum_size = device_property(dtype=int)
    folder_location = device_property(dtype=str)

    @attribute(label="error", dtype=int, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ, polling_period=1,
               abs_change='1')
    def internal_counter(self):
        return self._internal_counter

    def init_device(self):
        self.file_h5: h5py.File = None
        self.file_working: Path = None
        self.lock = False
        self._internal_counter = 0
        self.close_thread = Thread(target=self.closing, args=[5])
        super().init_device()
        self.folder_location = Path(self.folder_location)
        if not self.folder_location.exists():
            self.folder_location.mkdir(parents=True, exist_ok=True)
        self.turn_on()
        self.close_thread.start()

        data = self.form_acrhive_data(np.array([1024, 1024]).reshape((1, 2)), 'cg')
        msg_b = msgpack.packb(str(data))
        msg_b_c = zlib.compress(msg_b)
        msg_b_c_s = str(msg_b_c)
        self.archive_it(msg_b_c_s)

    def internal_time(self):
        while True:
            self._internal_counter += 1
            sleep(1)

    def closing(self, time):
        while True:
            sleep(5)
            if self.file_h5:
                if not self.lock:
                    self.close_h5()
                else:
                    while self.lock:
                        sleep(0.01)
                    self.close_h5()

    @command(dtype_in=str, dtype_out=str)
    def archive_it(self, data_string):
        state_ok = self.check_func_allowance(self.archive_it)
        if state_ok == 1:
            result = '0'
            try:
                self.lock = True
                self.file_size_check(self.file_working)
                self.open_h5()
                if not self.file_h5:
                    self.error('Cannot open h5 file.')
                    return 'Cannot open h5 file.'
                else:
                    data_bytes = eval(data_string)
                    data = zlib.decompress(data_bytes)
                    data = msgpack.unpackb(data, strict_map_key=False)
                    data: ArchiveData = eval(data)
                    data_to_archive = None
                    if isinstance(data.data, Scalar):
                        data_to_archive = np.array([data.data.value])
                    elif isinstance(data.data, Array):
                        data_to_archive = data.data.value
                        data_to_archive = np.frombuffer(data_to_archive, dtype=data.data.dtype).reshape(data.data.shape)
                    self.info(f'DATA to archive: {data_to_archive}', DEV)

                    ts = float(data.data_timestamp)
                    dt = datetime.fromtimestamp(ts)
                    date_as_str = dt.date().__str__()
                    group_date = self.check_group(self.file_h5, date_as_str)
                    group_device = self.check_group(group_date, data.tango_device)
                    shape = data_to_archive.shape

                    if len(shape) == 1:
                        maxshape = (None,)
                    elif len(shape) == 2:
                        maxshape = (None, data_to_archive.shape[1])
                    elif len(shape) == 3:
                        maxshape = (None, data_to_archive.shape[1], data_to_archive.shape[2])

                    self.dataset_update(group_device, data.dataset_name, shape=shape,
                                        maxshape=maxshape, dtype=np.dtype(data.data.dtype),
                                        data=data_to_archive)
                    ts_array = np.array([ts], dtype='float32')
                    self.dataset_update(group_device, f'{data.dataset_name}_timestamp', (ts_array.shape[0],),
                                        (None,), ts_array.dtype, ts_array)
            except Exception as e:
                self.error(e)
                result = str(e)
            finally:
                self.lock = False
                return result
        else:
            return f'Not allowed {self.get_state()}'

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
            ds = container.create_dataset(name=dataset_name, shape=shape, maxshape=maxshape, dtype=dtype, data=data)

    def create_new_h5(self, latest=None):
        if latest:
            stem = latest.stem
            idx = int(stem.split('_')[-1])
            file = self.folder_location / f'Data_pyconlyse_{idx}.hdf5'
        else:
            file = self.folder_location / 'Data_pyconlyse_1.hdf5'
        self.info(f'Creating new file: {file}', True)
        self.file_working = file

    @command(dtype_out=int)
    def open_h5(self):
        if not self.file_h5:
            file = str(self.file_working)
            self.info(f'Openning file: {file}')
            self.file_h5 = h5py.File(file, 'a')
        return 0

    @command(dtype_out=int)
    def close_h5(self):
        if self.file_h5:
            file = str(self.file_working)
            self.info(f'Closing file: {file}')
            self.file_h5.close()
            self.file_h5 = None
        return 0

    @attribute(label="error", dtype=int, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ)
    def is_h5_opened(self):
        if self.file_h5:
            return 1
        else:
            return 0

    def file_size_check(self, file):
        if file.stat().st_size < self.maximum_size:
            self.file_working = file
        else:
            self.create_new_h5(latest=file)

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
            self.file_size_check(file)
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
        self.set_state(DevState.OFF)
        return 0


if __name__ == "__main__":
   DS_Archive.run_server()
