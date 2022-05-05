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

    def _object_name_to_names(self, object_name):
        object_name_split = object_name.split('/')
        names = []
        if object_name_split[0] == 'any_date' and len(object_name_split) > 1:
            for date in list(self.h5_file.keys()):
                name = f'{date}/{"/".join(object_name_split[1:])}'
                names.append(name)
        else:
            names.append(object_name)
        return names

    def get_object(self, object_name):
        res = []
        object_names = self._object_name_to_names(object_name)
        for name in object_names:
            if name in self.h5_file:
                obj = self.h5_file.get(name)
                res.append(obj)
        return res

    def open(self, lock=False):
        if not self.h5_file:
            self.lock = True
            # self.parent.info(f'Openning file: {self.file_path}')
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
        object_names = self._object_name_to_names(object_name)
        res = []
        for name in object_names:
            if name in self.h5_file:
                res.append(True)
            else:
                res.append(False)
        return any(res)

    def dataset_update(self, dataset_name, shape, maxshape, dtype, data):
        if dataset_name in self.h5_file:
            ds = self.h5_file[dataset_name]
            ds.resize((ds.shape[0] + data.shape[0]), axis=0)
            ds[-data.shape[0]:] = data
        else:
            self.h5_file.create_dataset(name=dataset_name, shape=shape, maxshape=maxshape, dtype=dtype, data=data)


DEV = False


class DS_Archive(DS_General):
    RULES = {'archive_it': [DevState.ON], **DS_General.RULES}

    _version_ = '0.4'
    _model_ = 'DS_Archiving'
    polling_local = 25
    maximum_size = device_property(dtype=int)
    folder_location = device_property(dtype=str)

    @command(dtype_in=str, dtype_out=str, doc_in="String as 'device_name'_'data_as_str'")
    def archive_it_labview(self, data_string: str):
        dataset, data, timestamp = data_string.split(':')
        labview_var_split = dataset.split('/')
        device_name = '/'.join(labview_var_split[0:-1])
        dataset = labview_var_split[-1]
        data = float(data)
        timestamp = float(timestamp)
        data_to_archive = ArchiveData(tango_device=device_name, dataset_name=dataset, data_timestamp=timestamp,
                                      data=Scalar(data, 'float'))
        data_to_archive = self.compress_data(data_to_archive)
        return self.archive_it(data_to_archive)

    @command(dtype_in=str, dtype_out=str,
             doc_in="ArchiveData converted to string and compressed using zlib and msgpack")
    def archive_it(self, data_string):
        state_ok = self.check_func_allowance(self.archive_it)
        if state_ok == 1:
            result = '0'
            try:
                actual_h5_container: H5_container = self.get_actual_container()
                actual_h5_container.open(lock=True)
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
                    ts_array = np.array([ts], dtype='float')

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

    @command(dtype_in=[str], dtype_out=str, doc_in="array of string [dataset_name, timestamp_from, timestamp_to, "
                                                   "average]")
    def get_data(self, value):
        dataset_name = value[0]
        timestamp_from: int = int(value[1])  # timestamp
        timestamp_to: int = int(value[2])  # timestamp
        average = 1
        if len(value) == 4:
            average = int(value[3])
        res = b''
        containers: List[H5_container] = self.search_object(dataset_name)

        data_containers = []
        data_timestamps_containers = []

        for container in containers:
            container.open(True)
            items = container.get_object(dataset_name)
            item_timestamps = container.get_object(f'{dataset_name}_timestamp')
            for item, item_timestamp in zip(items, item_timestamps):
                if isinstance(item, h5py.Dataset):
                    data_containers.append(item)
                    data_timestamps_containers.append(item_timestamp)

        if data_containers and data_timestamps_containers:
            timestamp_max_values = [data_timestamp[-1] for data_timestamp in data_timestamps_containers]
            timestamp_min_values = [data_timestamp[0] for data_timestamp in data_timestamps_containers]

            order = np.argsort(timestamp_max_values)

            data_timestamps_containers_ordered = []
            data_containers_ordered = []

            for idx in order:
                data_timestamps_containers_ordered.append(data_timestamps_containers[idx])
                data_containers_ordered.append(data_containers[idx])

            if timestamp_to == -1:
                timestamp_to = np.max(timestamp_max_values)
            if timestamp_from == -1:
                timestamp_from = np.min(timestamp_min_values)

            def search_for_value(dataset: h5py.Dataset, value):
                return True if value in dataset else False

            def form_data(timestamps_containers: List[h5py.Dataset], data_containers: List[h5py.Dataset],
                          time_from: int, time_to: int) -> Tuple[numpy.ndarray]:

                indexes_of_containers = [-1, -1]
                # min index
                for timestamp_dataset, index in zip(timestamps_containers, range(len(timestamps_containers))):
                    res = search_for_value(timestamp_dataset, time_from)
                    if res:
                        indexes_of_containers[0] = index
                        break
                # max index
                for timestamp_dataset, index in zip(timestamps_containers, range(len(timestamps_containers))):
                    res = search_for_value(timestamp_dataset, time_to)
                    if res:
                        indexes_of_containers[1] = index
                        break

                if indexes_of_containers[0] == -1:
                    time_from = timestamps_containers[0][0]
                    indexes_of_containers[0] = 0
                if indexes_of_containers[1] == -1:
                    indexes_of_containers[1] = len(timestamps_containers) - 1
                    time_to = timestamps_containers[-1][-1]

                # form data
                timestamps = []
                data = []
                for idx in range(indexes_of_containers[0], indexes_of_containers[1] + 1):
                    timestamps.append(timestamps_containers[idx][:])
                    data.append(data_containers[idx][:])

                timestamps = np.concatenate(timestamps)[:]
                data = np.concatenate(data)[:]

                indexes_lower = [idx[0] for idx in np.argwhere(timestamps <= time_to)]
                timestamps = timestamps[indexes_lower]
                data = data[indexes_lower]
                indexes_upper = [idx[0] for idx in np.argwhere(timestamps >= time_from)]
                timestamps = timestamps[indexes_upper]
                data = data[indexes_upper]

                return timestamps, data


            data_timestamps, data = form_data(data_timestamps_containers_ordered, data_containers_ordered,
                                              timestamp_from, timestamp_to)

            if average != 1:
                for i in range(len(data_timestamps)):
                    if (len(data_timestamps) + i) % average == 0:
                        break
                if i != 0:
                    data_timestamps = np.pad(data_timestamps, [0, i], mode='constant')

                if len(data.shape) == 1:
                    data = np.pad(data, [0, i], mode='constant')
                elif len(data.shape) == 2:
                    data = np.pad(data, ([0, 1], [0, 0]), mode='constant')


                data_timestamps = np.average(data_timestamps.reshape(-1, average), axis=1).astype(data_timestamps.dtype)
                data = np.average(data.reshape(-1, average), axis=1).astype(data.dtype)

            # check that data does not exceed 10000 points
            data_timestamps = data_timestamps[0:10000]
            data = data[0:10000]

            dataXY = DataXYb(X=data_timestamps.tobytes(), Y=data.tobytes(), name=dataset_name,
                             Xdtype=str(data_timestamps.dtype), Ydtype=str(data.dtype))

            res = self.compress_data(dataXY)
        for container in containers:
            container.lock = False
        return res

    @command(dtype_in=str, dtype_out=str)
    def get_info_object(self, object_name):
        containers: List[H5_container] = self.search_object(object_name)
        result = 'Nothing to tell you about'
        if containers:
            size = 0
            shape = [0, 0]
            for container in containers:
                container.open(True)
                objects = container.get_object(object_name)
                for object in objects:
                    if isinstance(object, h5py.Dataset):
                        size += object.nbytes
                        if len(object.shape) == 1:
                            shape[0] += object.shape[0]
                        elif len(object.shape) == 2:
                            shape[0] += object.shape[0]
                            shape[1] += object.shape[1]

                        result = f'Shape: {shape}; Maxshape: {object.maxshape}, ' \
                                 f'Size: {size / 1024} kB, {object.dtype}'
                container.lock = False
        return result

    @command(dtype_in=str, dtype_out=str)
    def get_object_timestamps(self, value):
        dataset_name = value
        res = [datetime.now().timestamp(), datetime.now().timestamp()]
        containers: List[H5_container] = self.search_object(dataset_name)

        data_timestamps_containers = []

        for container in containers:
            container.open(True)
            item_timestamps = container.get_object(f'{dataset_name}_timestamp')
            for item_timestamp in item_timestamps:
                if isinstance(item_timestamp, h5py.Dataset):
                    data_timestamps_containers.append(item_timestamp)

        if data_timestamps_containers:
            timestamp_max = max([data_timestamp[-1] for data_timestamp in data_timestamps_containers])
            timestamp_min = min([data_timestamp[0] for data_timestamp in data_timestamps_containers])
            res = [timestamp_min, timestamp_max]
        res = str(res).encode('utf-8')
        return res

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
        self.register_variables_for_archive()
        self.turn_on()
        # self.get_info_object('any_date/elyse/modulator/focale1/current/value')
        # self.get_data(['any_date/elyse/modulator/focale1/current/value', '-1', '-1', '7'])
        # self.archive_it_labview('elyse/timestamp:3734421386.935:1.651572987049E+9')
        # self.get_object_timestamps('any_date/elyse/modulator/focale1/current/value')

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
            container.open(True)
            res = container.is_object_present(object_name)
            if res:
                group.append(container)
            container.close()
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

    def register_variables_for_archive(self):
        super().register_variables_for_archive()


if __name__ == "__main__":
   DS_Archive.run_server()
