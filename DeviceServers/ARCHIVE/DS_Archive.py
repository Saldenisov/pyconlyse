#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys

from pathlib import Path
from typing import Union, Tuple
from datetime import datetime

import numpy

app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))
from tango import AttrWriteType, DispLevel, DevState
from threading import Thread
from time import sleep
from DeviceServers.General.DS_general import DS_General, standard_str_output
import h5py
from dataclasses import dataclass, field

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property
from typing import Union, Tuple, Dict, Any, List

from DeviceServers.General.DS_general import DS_General, standard_str_output
import zlib
import msgpack
from utilities.datastructures.mes_independent.measurments_dataclass import ArchiveData, Scalar, Array, DataXYb
import numpy as np
from numpy import array

uint8 = np.dtype('uint8')
int16 = np.dtype('int16')
# Keep this to make everything work
__a = array([1])


@dataclass
class H5_container:
    file_path: Path
    parent: object
    close_thread: Thread = None
    h5_file: h5py.File = None
    lock: bool = False
    close_time: int = 5

    def __post_init__(self):
        self.open()
        self._structure = {}
        self._prev_size = self.file_path.stat().st_size
        self.close_thread = Thread(target=self.closing)
        self.close_thread.start()
        self.create_structure()

    def get_object(self, object_name):
        self.open()
        return self.h5_file.get(object_name)

    def open(self, lock=False):
        if not self.h5_file:
            self.lock = True
            self.parent.info(f'Openning file: {self.file_path}')
            self.h5_file = h5py.File(str(self.file_path), 'a')
        self.lock = lock

    def close(self):
        self.h5_file.close()
        self.h5_file = None
        self.lock = False

    @property
    def structure(self):
        if not self._structure or (self.file_path.stat().st_size != self._prev_size):
            self.create_structure()
        return self._structure

    def create_structure(self):
        def fill_keys(d, obj):
            if len(obj.keys()) == 0:
                return None
            else:
                for key in obj.keys():
                    if isinstance(obj[key], h5py.Dataset):
                        d[key] = None
                    else:
                        d[key] = {}
                        d[key] = fill_keys(d[key], obj[key])
                return d
        structure = {}
        self.open()
        if len(self.h5_file.keys()) != 0:
            structure = fill_keys(structure, self.h5_file)
        self._structure = structure

    def closing(self):
        while True:
            sleep(self.close_time)
            if self.h5_file:
                if not self.lock:
                    self.close()

    def is_object_present(self, object_name: str):
        self.open()
        if object_name in self.h5_file:
            return True
        else:
            return False

    def dataset_update(self, dataset_name, shape, maxshape, dtype, data):
        self.open()
        self.lock = True
        if dataset_name in self.h5_file:
            ds = self.h5_file[dataset_name]
            ds.resize((ds.shape[0] + data.shape[0]), axis=0)
            ds[-data.shape[0]:] = data
        else:
            self.h5_file.create_dataset(name=dataset_name, shape=shape, maxshape=maxshape, dtype=dtype, data=data)
        self.lock = False


DEV = False


class DS_Archive(DS_General):
    RULES = {'archive_it': [DevState.ON], **DS_General.RULES}

    _version_ = '0.4'
    _model_ = 'DS_Archiving'
    polling_local = 25
    maximum_size = device_property(dtype=int)
    folder_location = device_property(dtype=str)

    @command(dtype_in=str, dtype_out=str)
    def archive_it(self, data_string):
        state_ok = self.check_func_allowance(self.archive_it)
        if state_ok == 1:
            result = '0'
            try:
                actual_h5_container = self.get_actual_container()
                actual_h5_container.open()
                actual_h5_container.lock = True
                file_h5 = actual_h5_container.h5_file
                if not file_h5:
                    error = f'Cannot open h5 file {actual_h5_container.file_path}.'
                    self.error(error)
                    return error
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
                    dataset_name_h5 = f'{date_as_str}/{data.tango_device}/{data.dataset_name}'
                    shape = data_to_archive.shape

                    if len(shape) == 1:
                        maxshape = (None,)
                    elif len(shape) == 2:
                        maxshape = (None, data_to_archive.shape[1])
                    elif len(shape) == 3:
                        maxshape = (None, data_to_archive.shape[1], data_to_archive.shape[2])

                    actual_h5_container.dataset_update(dataset_name_h5, shape=shape, maxshape=maxshape,
                                                       dtype=np.dtype(data.data.dtype), data=data_to_archive)
                    ts_array = np.array([ts], dtype='float32')
                    actual_h5_container.dataset_update(f'{dataset_name_h5}_timestamp',
                                                       (ts_array.shape[0],), (None,), ts_array.dtype, ts_array)
            except Exception as e:
                self.error(e)
                result = str(e)
            finally:
                actual_h5_container.lock = False
                return result
        else:
            return f'Not allowed {self.get_state()}'

    @attribute(label="Archive structure as dict", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ)
    def archive_structure(self):
        structure = {}
        for container in self.containers_h5.values():
            structure.update(container.structure)
        return str(structure)

    @attribute(label="Archive devices as list", dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ)
    def archive_devices(self):
        devices = set([])
        for container in self.containers_h5.values():
            container.update_structure()
            devices.update(container.devices_list)
        return str(devices)

    def add_file(self, file: Path, close_time=5):
        self.containers_h5[file] = H5_container(file_path=file, parent=self, close_time=close_time)

    def create_new_h5(self, latest=None):
        if latest:
            stem = latest.stem
            idx = int(stem.split('_')[-1])
            file = self.folder_location / f'Data_pyconlyse_{idx + 1}.hdf5'
        else:
            file = self.folder_location / 'Data_pyconlyse_1.hdf5'
        self.info(f'Creating new file: {file}', True)
        self.file_working = file
        self.add_file(file, 2)

    def get_actual_container(self) -> H5_container:
        self.file_size_check(self.file_working)
        return self.containers_h5[self.file_working]

    def form_archive_files(self):
        archive_files = list(self.folder_location.glob('*.hdf5'))
        for file_name in archive_files:
            file_path = self.folder_location / file_name
            self.add_file(file_path, 2)

    def find_device(self) -> Tuple[int, str]:
        arg_return = 1, b'qwerty'
        self.info(f"Searching for Archive device {self.device_name}", True)
        self._device_id_internal, self._uri = arg_return
        return arg_return

    @command(dtype_in=[str], dtype_out=str)
    def get_data(self, value):
        dataset_name = value[0]
        timestamp_from: int = int(value[1])  # timestamp
        timestamp_to: int = int(value[2])  # timestamp
        res = b''
        containers: List[H5_container] = self.search_object(dataset_name)

        data = []
        data_timestamps = []

        for container in containers:
            container.open(True)
            item = container.get_object(dataset_name)
            if isinstance(item, h5py.Dataset):
                dataset = item[:]
                dataset_timestamp = container.get_object(f'{dataset_name}_timestamp')[:]
                if len(dataset.shape) == 1:
                    data.append(dataset)
                    data_timestamps.append(dataset_timestamp)

        if data and data_timestamps:
            timestamp_max_values = [data_timestamp[-1] for data_timestamp in data_timestamps]

            order = np.argsort(timestamp_max_values)

            data_timestamps_ordered = []
            data_ordered = []

            for idx in order:
                data_timestamps_ordered.append(data_timestamps[idx])
                data_ordered.append(data[idx])

            data_timestamps = numpy.concatenate(data_timestamps_ordered)[:]
            data = numpy.concatenate(data_ordered)[:]

            if timestamp_to == -1:
                timestamp_to = np.max(data_timestamps)
            if timestamp_from == -1:
                timestamp_from = np.min(data_timestamps)

            indexes_lower = [idx[0] for idx in np.argwhere(data_timestamps <= timestamp_to)]
            data_timestamps = data_timestamps[indexes_lower]
            data = data[indexes_lower]
            indexes_upper = [idx[0] for idx in np.argwhere(data_timestamps >= timestamp_from)]
            data_timestamps = data_timestamps[indexes_upper]
            data = data[indexes_upper]

            dataXY = DataXYb(X=data_timestamps.tobytes(), Y=data.tobytes(),
                             name=dataset_name, Xdtype=str(data_timestamps.dtype), Ydtype=str(data.dtype))

            res = self.compress_data(dataXY)
        for container in containers:
            container.lock = False
        return res

    @command(dtype_in=str, dtype_out=str)
    def get_info_object(self, object_name):
        containers: List[H5_container] = self.search_object(object_name)

        result = []
        if containers:
            for container in containers:
                object = container.get_object(object_name)
                if isinstance(object, h5py.Dataset):
                    info = f'Shape: {object.shape}; Maxshape: {object.maxshape}, ' \
                           f'Size: {object.nbytes / 1024} kB, {object.dtype}'
                    result.append(info)
        if result:
            result_str = '. '.join(result)
        else:
            result_str = 'Nothing to tell you about'
        return result_str

    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    @attribute(label="error", dtype=int, display_level=DispLevel.OPERATOR, access=AttrWriteType.READ, polling_period=1,
               abs_change='1')
    def internal_counter(self):
        return self._internal_counter

    def init_device(self):
        self.dates_files = {}
        self.containers_h5: Dict[Path, H5_container] = {}
        self.file_working: Path = None
        self._internal_counter = 0
        super().init_device()
        self.folder_location = Path(self.folder_location)
        if not self.folder_location.exists():
            self.folder_location.mkdir(parents=True, exist_ok=True)
        self.latest_h5()
        self.turn_on()
        self.get_data(['2022-04-12/ELYSE/motorized_devices/DE1/position', '-1', '-1'])

    def internal_time(self):
        while True:
            self._internal_counter += 1
            sleep(1)

    def file_size_check(self, file: Path):
        if file.stat().st_size < self.maximum_size:
            self.file_working = file
        else:
            self.create_new_h5(latest=file)

    def latest_h5(self):
        self.form_archive_files()
        if self.containers_h5:
            latest = 0
            latest_file: Path = None
            for file in self.containers_h5.keys():
                if latest < file.stat().st_ctime:
                    latest = file.stat().st_ctime
                    latest_file = file
            self.file_size_check(latest_file)
        else:
            self.create_new_h5()

    def search_object(self, object_name: str) -> List[H5_container]:
        group = []
        for container in self.containers_h5.values():
            res = container.is_object_present(object_name)
            if res:
                group.append(container)
        return group

    def turn_on_local(self) -> Union[int, str]:
        container = self.get_actual_container()
        container.open()
        if container.h5_file:
            self.set_state(DevState.ON)
        else:
            self.set_state(DevState.FAULT)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        container = self.get_actual_container()
        container.close()
        self.set_state(DevState.OFF)
        return 0


if __name__ == "__main__":
   DS_Archive.run_server()
