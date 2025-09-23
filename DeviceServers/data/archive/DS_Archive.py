#!/usr/bin/env python


import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Tuple, Union

import numpy

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))
import base64
import json
import random
import shutil
import string
import zlib
from dataclasses import dataclass
from threading import Thread
from time import sleep
from typing import Dict, List

import h5py
import msgpack
import numpy as np
from numpy import array
from tango import AttrWriteType, DevState, DispLevel
from tango.server import attribute, command, device_property

from DeviceServers.base.DS_general import DS_General
from utilities.datastructures.mes_independent.measurments_dataclass import (
    ArchiveData,
    Array,
    DataXYb,
    Scalar,
)

uint8 = np.dtype("uint8")
int16 = np.dtype("int16")
# Keep this to make everything work
__a = array([1])


@dataclass
class Order:
    order_param: List[str]
    timestamp: int
    started: bool = False
    order_done: bool = False
    ready_to_delete: bool = False
    order_res: str = ""


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
        object_name_split = object_name.split("/")
        names = []
        if object_name_split[0] == "any_date" and len(object_name_split) > 1:
            for date in list(self.h5_file.keys()):
                name = f"{date}/{'/'.join(object_name_split[1:])}"
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

    def get_shape(self):
        self.open()
        return self.shape()

    def open(self, lock=False):
        if not self.h5_file:
            self.lock = True
            self.h5_file = h5py.File(str(self.file_path), "a")
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
            for key in obj.keys():
                if isinstance(obj[key], h5py.Dataset):
                    d[key] = None
                else:
                    d[key] = {}
                    d[key] = fill_keys(d[key], obj[key])
            return d

        structure = {}
        self.open(lock=True)
        if len(self.h5_file.keys()) != 0:
            structure = fill_keys(structure, self.h5_file)
        self.lock = False
        print(f"Structure is creating for {self.file_path}")
        self._structure = structure

    def update_structure(self):
        # Refreshes the cached structure map
        self.create_structure()

    @property
    def devices_list(self) -> List[str]:
        # Returns a list of device paths (without dates and dataset names)
        devices: set = set()

        def collect_devices(node: dict, prefix: str = ""):
            for key, val in node.items():
                if val is None:
                    if prefix:
                        devices.add(prefix.rstrip("/"))
                else:
                    new_prefix = f"{prefix}/{key}" if prefix else key
                    collect_devices(val, new_prefix)

        # Top-level keys are dates; skip them and traverse children
        for date_key, sub in self.structure.items():
            if isinstance(sub, dict):
                collect_devices(sub, "")
        return sorted(devices)

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
            ds[-data.shape[0] :] = data
        else:
            self.h5_file.create_dataset(
                name=dataset_name,
                shape=shape,
                maxshape=maxshape,
                dtype=dtype,
                data=data,
            )


DEV = True


# -------- Safe serialization helpers --------
# We support a new base64-encoded payload and also the legacy 'str(bytes)' payload for backward compatibility.
B64_PREFIX = "b64:"


def _archive_to_payload_dict(data: ArchiveData) -> dict:
    if isinstance(data.data, Scalar):
        payload_data = {
            "kind": "Scalar",
            "value": data.data.value,
            "dtype": data.data.dtype,
        }
    elif isinstance(data.data, Array):
        payload_data = {
            "kind": "Array",
            "value": base64.b64encode(data.data.value).decode("ascii"),
            "shape": list(data.data.shape),
            "dtype": data.data.dtype,
        }
    else:
        raise ValueError("Unsupported data type in ArchiveData")
    return {
        "version": 1,
        "kind": "ArchiveData",
        "tango_device": data.tango_device,
        "dataset_name": data.dataset_name,
        "data_timestamp": float(data.data_timestamp),
        "data": payload_data,
    }


def _payload_dict_to_archive(d: dict) -> ArchiveData:
    if not isinstance(d, dict) or d.get("kind") != "ArchiveData":
        raise ValueError("Invalid payload: not an ArchiveData dict")
    pdata = d.get("data", {})
    if pdata.get("kind") == "Scalar":
        data_field = Scalar(value=float(pdata["value"]), dtype=str(pdata["dtype"]))
    elif pdata.get("kind") == "Array":
        raw = (
            base64.b64decode(pdata["value"])
            if isinstance(pdata.get("value"), str)
            else pdata.get("value", b"")
        )
        shape = tuple(pdata.get("shape", []))
        dtype = str(pdata.get("dtype", "float"))
        data_field = Array(value=raw, shape=shape, dtype=dtype)
    else:
        raise ValueError("Invalid payload: unknown data.kind")
    return ArchiveData(
        tango_device=str(d["tango_device"]),
        data_timestamp=float(d["data_timestamp"]),
        dataset_name=str(d["dataset_name"]),
        data=data_field,
    )


def encode_archive_payload(data: ArchiveData) -> str:
    packed = msgpack.packb(_archive_to_payload_dict(data), use_bin_type=True)
    compressed = zlib.compress(packed)
    return B64_PREFIX + base64.b64encode(compressed).decode("ascii")


def decode_archive_payload(data_string: str) -> ArchiveData:
    # New format: b64:<base64(zlib(msgpack(dict)))>
    if isinstance(data_string, bytes):
        data_string = data_string.decode("utf-8")
    if str(data_string).startswith(B64_PREFIX):
        b64 = data_string[len(B64_PREFIX) :]
        compressed = base64.b64decode(b64)
        unpacked = msgpack.unpackb(zlib.decompress(compressed), raw=False)
        return _payload_dict_to_archive(unpacked)
    # Legacy format: str(bytes(zlib(msgpack(str(dataclass))))) -> eval
    try:
        data_bytes = eval(data_string)
        data = zlib.decompress(data_bytes)
        unpacked = msgpack.unpackb(data, strict_map_key=False)
        # unpacked here is a string representation of dataclass, legacy path
        return eval(unpacked)
    except Exception as e:
        raise ValueError(f"Failed to decode payload: {e}")


class DS_Archive(DS_General):
    RULES = {
        "archive_it": [DevState.ON],
        "archive_it_labview": [DevState.ON],
        **DS_General.RULES,
    }

    _version_ = "0.5"
    _model_ = "DS_Archiving"
    polling_local = 25
    maximum_size = device_property(dtype=int)
    folder_location = device_property(dtype=str)

    @command(
        dtype_in=str, dtype_out=str, doc_in="String as 'device_name'_'data_as_str'"
    )
    def archive_it_labview(self, data_string: str):
        dataset, data, timestamp = data_string.split(":")
        labview_var_split = dataset.split("/")
        device_name = "/".join(labview_var_split[0:-1])
        dataset = labview_var_split[-1]
        data = float(data)
        timestamp = float(timestamp)
        data_to_archive = ArchiveData(
            tango_device=device_name,
            dataset_name=dataset,
            data_timestamp=timestamp,
            data=Scalar(data, "float"),
        )
        # Use safe payload encoding
        payload = encode_archive_payload(data_to_archive)
        return self.archive_it(payload)

    @command(
        dtype_in=str,
        dtype_out=str,
        doc_in="ArchiveData converted to string and compressed using zlib and msgpack.",
    )
    def archive_it(self, data_string):
        state_ok = self.check_func_allowance(self.archive_it)
        if state_ok == 1:
            result = "0"
            try:
                actual_h5_container: H5_container = self.get_actual_container()
                actual_h5_container.open(lock=True)
                file_h5 = actual_h5_container.h5_file

                if not file_h5:
                    error = f"Cannot open h5 file {actual_h5_container.file_path}."
                    self.error(error)
                    return error
                # Decode payload (supports both legacy and new safe format)
                data: ArchiveData = decode_archive_payload(data_string)
                data_to_archive = None
                self.comment = f"Archiving for {data.tango_device}."
                if isinstance(data.data, Scalar):
                    data_to_archive = np.array([data.data.value])
                elif isinstance(data.data, Array):
                    data_to_archive = data.data.value
                    data_to_archive = np.frombuffer(
                        data_to_archive, dtype=data.data.dtype
                    ).reshape(data.data.shape)

                ts = float(data.data_timestamp)
                dt = datetime.fromtimestamp(ts)
                date_as_str = dt.date().__str__()
                dataset_name_h5 = (
                    f"{date_as_str}/{data.tango_device}/{data.dataset_name}"
                )
                shape = data_to_archive.shape

                if len(shape) == 1:
                    maxshape = (None,)
                elif len(shape) == 2:
                    maxshape = (None, data_to_archive.shape[1])
                elif len(shape) == 3:
                    maxshape = (
                        None,
                        data_to_archive.shape[1],
                        data_to_archive.shape[2],
                    )

                actual_h5_container.dataset_update(
                    dataset_name_h5,
                    shape=shape,
                    maxshape=maxshape,
                    dtype=np.dtype(data.data.dtype),
                    data=data_to_archive,
                )
                ts_array = np.array([ts], dtype="float")

                actual_h5_container.dataset_update(
                    f"{dataset_name_h5}_timestamp",
                    (ts_array.shape[0],),
                    (None,),
                    ts_array.dtype,
                    ts_array,
                )
            except Exception as e:
                self.error(e)
                result = str(e)
            finally:
                actual_h5_container.lock = False
                return result
        else:
            return f"Not allowed {self.get_state()}"

    @attribute(
        label="Archive structure as dict",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def archive_structure(self):
        structure = {}
        for container in self.containers_h5.values():
            structure.update(container.structure)
        return str(structure)

    @attribute(
        label="Archive devices as list",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def archive_devices(self):
        devices = set([])
        for container in self.containers_h5.values():
            container.update_structure()
            devices.update(container.devices_list)
        return str(devices)

    def add_file(self, file: Path, close_time=5):
        self.containers_h5[file] = H5_container(
            file_path=file, parent=self, close_time=close_time
        )

    def create_new_h5(self, latest=None):
        if latest:
            stem = latest.stem
            idx = int(stem.split("_")[-1])
            file = self.folder_location / f"Data_pyconlyse_{idx + 1}.hdf5"
        else:
            file = self.folder_location / "Data_pyconlyse_1.hdf5"
        self.info(f"Creating new file: {file}", True)
        self.file_working = file
        self.add_file(file, 2)

    def get_actual_container(self) -> H5_container:
        self.file_size_check(self.file_working)
        return self.containers_h5[self.file_working]

    def form_archive_files(self):
        archive_files = list(self.folder_location.glob("*.hdf5"))
        for file_name in archive_files:
            file_path = self.folder_location / file_name
            self.add_file(file_path, 2)

    def find_device(self) -> Tuple[int, str]:
        arg_return = 1, b"qwerty"
        self.info(f"Searching for Archive device {self.device_name}", True)
        self._device_id_internal, self._uri = arg_return
        return arg_return

    @command(dtype_in=str, doc_in="Order name", dtype_out=bool)
    def is_order_ready(self, name):
        res = False
        if name in self.orders:
            order = self.orders[name]
            res = order.order_done
        return res

    @command(dtype_in=str, doc_in="Order name", dtype_out=str)
    def give_order(self, name):
        order = b""
        if name in self.orders:
            order: Order = self.orders[name]
            order.ready_to_delete = True
        return str(order.order_res)

    @command(
        dtype_in=[str],
        dtype_out=str,
        doc_in="array of string [dataset_name, timestamp_from average, n_of_points]",
        doc_out="Return name of order.",
    )
    def get_data(self, value):
        s = 20  # number of characters in the string.
        name = "".join(random.choices(string.ascii_uppercase + string.digits, k=s))
        self.orders[name] = Order(order_param=value, timestamp=time.time())
        return name

    def _get_data(self, order_name: str):
        value = self.orders[order_name].order_param
        self.orders[order_name].started = True
        print(f"Executing command {value}")
        dataset_name = value[0]
        from_idx: int = int(value[1])  # timestamp
        average = 1
        n_of_points = 10000

        if len(value) >= 3:
            average = int(value[2])
        if len(value) >= 4:
            n_of_points = int(value[3])
        res = b""
        containers: List[H5_container] = self.search_object(dataset_name)

        data_containers = []
        data_timestamps_containers = []

        for container in containers:
            container.open(lock=True)
            items = container.get_object(dataset_name)
            item_timestamps = container.get_object(f"{dataset_name}_timestamp")
            for item, item_timestamp in zip(items, item_timestamps):
                if isinstance(item, h5py.Dataset) and item.shape[0] >= 1:
                    data_containers.append(np.array(item))
                    data_timestamps_containers.append(np.array(item_timestamp))

        if data_containers and data_timestamps_containers:
            timestamp_max_values = [
                data_timestamp[-1] for data_timestamp in data_timestamps_containers
            ]

            order = np.argsort(timestamp_max_values)

            data_timestamps_containers_ordered = []
            data_containers_ordered = []

            for idx in order:
                data_timestamps_containers_ordered.append(
                    data_timestamps_containers[idx]
                )
                data_containers_ordered.append(data_containers[idx])

            def form_data(
                timestamps_containers: List[h5py.Dataset],
                data_containers: List[h5py.Dataset],
                from_idx=0,
                n_of_points=10000,
                average=1,
            ) -> Tuple[numpy.ndarray]:
                indexes_of_containers = [0, -1]
                # min index
                length = 0
                for timestamp_dataset, index in zip(
                    timestamps_containers, range(len(timestamps_containers))
                ):
                    length += timestamp_dataset.shape[0]
                    if length >= from_idx:
                        indexes_of_containers[0] = index
                        break

                timestamps_containers = timestamps_containers[
                    indexes_of_containers[0] :
                ]
                data_containers = data_containers[indexes_of_containers[0] :]

                # max index
                length = 0
                for timestamp_dataset, index in zip(
                    timestamps_containers, range(len(timestamps_containers))
                ):
                    length += timestamp_dataset.shape[0]
                    indexes_of_containers[1] = index
                    if length >= n_of_points + from_idx:
                        break

                timestamps_containers = timestamps_containers[
                    : indexes_of_containers[1] + 1
                ]
                data_containers = data_containers[: indexes_of_containers[1] + 1]

                # form data
                timestamps = []
                data = []

                for timestamp_dataset, dataset in zip(
                    timestamps_containers, data_containers
                ):
                    number = n_of_points + from_idx
                    if timestamp_dataset.shape[0] >= number:
                        timestamps.append(timestamp_dataset[from_idx:number])
                        data.append(dataset[from_idx:number])
                        break
                    timestamps.append(timestamp_dataset[from_idx:])
                    data.append(dataset[from_idx:])
                    n_of_points -= len(timestamp_dataset) - from_idx
                    from_idx = 0

                timestamps = np.concatenate(timestamps)[:n_of_points]
                data = np.concatenate(data)[:n_of_points]

                if average != 1 and len(data) > 10 * average:
                    j = 0
                    for i in range(len(timestamps)):
                        if (len(timestamps) + i) % average == 0:
                            j = i
                            break
                    if j != 0:
                        timestamps = np.pad(timestamps, [0, j], mode="constant")

                    if len(data.shape) == 1:
                        data = np.pad(data, [0, j], mode="constant")
                    elif len(data.shape) == 2:
                        data = np.pad(data, ([0, j], [0, 0]), mode="constant")

                    timestamps = np.average(
                        timestamps.reshape(-1, average), axis=1
                    ).astype(timestamps.dtype)
                    data = np.average(data.reshape(-1, average), axis=1).astype(
                        data.dtype
                    )

                return timestamps, data

            try:
                data_timestamps, data = form_data(
                    data_timestamps_containers_ordered,
                    data_containers_ordered,
                    from_idx,
                    n_of_points,
                    average,
                )

                dataXY = DataXYb(
                    X=data_timestamps.tobytes(),
                    Y=data.tobytes(),
                    name=dataset_name,
                    Xdtype=str(data_timestamps.dtype),
                    Ydtype=str(data.dtype),
                )
                self.info("Data is formed.", DEV)
                res = self.compress_data(dataXY)
                for container in containers:
                    container.lock = False
            except Exception as e:
                self.error(e)
        self.orders[order_name].order_res = res
        self.orders[order_name].order_done = True

    @command(dtype_in=str, dtype_out=str)
    def get_info_object(self, object_name):
        containers: List[H5_container] = self.search_object(object_name)
        result = "Nothing to tell you about"
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

                        result = (
                            f"Shape: {shape}; Maxshape: {object.maxshape}, "
                            f"Size: {size / 1024} kB, {object.dtype}"
                        )
                container.lock = False
        return result

    @command(dtype_in=str, dtype_out=str)
    def get_object_timestamps(self, value):
        dataset_name = value
        res = [datetime.now().timestamp(), datetime.now().timestamp(), 0]
        containers: List[H5_container] = self.search_object(dataset_name)

        data_timestamps_containers = []

        for container in containers:
            container.open(True)
            item_timestamps = container.get_object(f"{dataset_name}_timestamp")
            for item_timestamp in item_timestamps:
                if isinstance(item_timestamp, h5py.Dataset):
                    data_timestamps_containers.append(item_timestamp)

        if data_timestamps_containers:
            timestamp_min = [
                data_timestamp[0] for data_timestamp in data_timestamps_containers
            ]
            timestamp_max = [
                data_timestamp[-1] for data_timestamp in data_timestamps_containers
            ]
            length = [
                len(data_timestamp) for data_timestamp in data_timestamps_containers
            ]
            res = [min(timestamp_min), max(timestamp_max), np.sum(length)]
        return str(res)

    def get_controller_status_local(self) -> Union[int, str]:
        return 0

    @attribute(
        label="error",
        dtype=int,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=1,
        abs_change="1",
    )
    def internal_counter(self):
        return self._internal_counter

    def init_device(self):
        self.orders: Dict[str, Order] = {}
        self.dates_files = {}
        self.containers_h5: Dict[Path, H5_container] = {}
        self.file_working: Path = None
        self._internal_counter = 0
        super().init_device()
        self.folder_location = Path(self.folder_location)
        if not self.folder_location.exists():
            self.folder_location.mkdir(parents=True, exist_ok=True)
        # Ensure projects directory exists
        self._projects_dir().mkdir(parents=True, exist_ok=True)
        self.latest_h5()
        self.register_variables_for_archive()
        self.orders_thread = Thread(target=self.execute_orders)
        self.turn_on()
        # c = self._get_data(Order(order_param=['2022-05-06/elyse/cooling/canon/temperature/measurement', '1651788000.0', '20', '10000'], timestamp=time.time()))
        self.orders_thread.start()
        # order_name = self.get_data(['2022-05-06/elyse/cooling/canon/temperature/measurement', '1651788000.0', '20', '10000'])
        # for i in range(60):
        #     ready = self.is_order_ready(order_name)
        #     if ready:
        #         break
        #     time.sleep(.5)
        # order = self.give_order(order_name)
        # self.archive_it_labview('elyse/timestamp:3734421386.935:1.651572987049E+9')
        # self.get_object_timestamps('any_date/elyse/modulator/focale1/current/value')

    def execute_orders(self):
        while True:
            sleep(0.1)
            if self.orders:
                orders_to_delete = []
                for order_name, order in self.orders.items():
                    if not order.order_done and not order.started:
                        print(f"Getting data for order: {order_name}.")
                        thread_get_data = Thread(
                            target=self._get_data, args=[order_name]
                        )
                        thread_get_data.start()
                    if order.ready_to_delete:
                        orders_to_delete.append(order_name)
                    if (time.time() - order.timestamp) >= 100:
                        orders_to_delete.append(order_name)
                if orders_to_delete:
                    for order_name in orders_to_delete:
                        del self.orders[order_name]

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

    # Utilities for project management
    def _projects_dir(self) -> Path:
        return self.folder_location / "projects"

    @staticmethod
    def _try_json(val: str):
        try:
            return json.loads(val)
        except Exception:
            return val

    # Project part

    @command(dtype_in=str, dtype_out=str, display_level=DispLevel.OPERATOR)
    def create_project(self, name: str):
        try:
            payload = self._try_json(name)
            if isinstance(payload, dict):
                project_name = str(payload.get("name", "")).strip()
                meta = payload.get("meta", {})
            else:
                project_name = str(payload).strip()
                meta = {}
            if not project_name:
                return 'ERROR: provide project name or {"name":...}'
            proj_dir = self._projects_dir() / project_name
            if proj_dir.exists():
                return f"ERROR: project '{project_name}' already exists"
            proj_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "name": project_name,
                "created_at": datetime.now().isoformat(),
                "meta": meta,
                "subprojects": {},
                "measurements": {},
            }
            with open(proj_dir / "project.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return f"OK: created project '{project_name}'"
        except Exception as e:
            return f"ERROR: {e}"

    @command(dtype_in=str, dtype_out=str, display_level=DispLevel.OPERATOR)
    def edit_project(self, name: str):
        try:
            payload = self._try_json(name)
            if not isinstance(payload, dict):
                return "ERROR: provide JSON {'name':..., 'set':{...}}"
            project_name = str(payload.get("name", "")).strip()
            to_set = payload.get("set", {})
            if not project_name:
                return "ERROR: 'name' missing"
            proj_dir = self._projects_dir() / project_name
            pfile = proj_dir / "project.json"
            if not pfile.exists():
                return f"ERROR: project '{project_name}' not found"
            with open(pfile, encoding="utf-8") as f:
                data = json.load(f)
            # Merge 'meta'
            if "meta" in to_set and isinstance(to_set["meta"], dict):
                data.setdefault("meta", {}).update(to_set["meta"])
            # Other top-level updates
            for k, v in to_set.items():
                if k != "meta":
                    data[k] = v
            with open(pfile, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return f"OK: edited project '{project_name}'"
        except Exception as e:
            return f"ERROR: {e}"

    @command(dtype_in=str, dtype_out=str, display_level=DispLevel.OPERATOR)
    def delete_project(self, name: str):
        try:
            project_name = str(
                self._try_json(name) if isinstance(self._try_json(name), str) else name
            ).strip()
            if not project_name:
                return "ERROR: provide project name"
            proj_dir = self._projects_dir() / project_name
            if not proj_dir.exists():
                return f"ERROR: project '{project_name}' not found"
            shutil.rmtree(proj_dir, ignore_errors=True)
            return f"OK: deleted project '{project_name}'"
        except Exception as e:
            return f"ERROR: {e}"

    @attribute(
        label="List of projects files",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
    )
    def list_of_projects(self):
        try:
            root = self._projects_dir()
            if not root.exists():
                return "[]"
            res = []
            for p in sorted([d for d in root.iterdir() if d.is_dir()]):
                pfile = p / "project.json"
                if pfile.exists():
                    with open(pfile, encoding="utf-8") as f:
                        data = json.load(f)
                    res.append(
                        {
                            "name": data.get("name", p.name),
                            "created_at": data.get("created_at", ""),
                        }
                    )
                else:
                    res.append({"name": p.name})
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @command(dtype_in=str, dtype_out=str, display_level=DispLevel.OPERATOR)
    def add_sub_project(self, value: str):
        try:
            payload = self._try_json(value)
            if not isinstance(payload, dict):
                return "ERROR: provide JSON {'project':..., 'name':...}"
            project = str(payload.get("project", "")).strip()
            name = str(payload.get("name", "")).strip()
            if not project or not name:
                return "ERROR: 'project' and 'name' required"
            pfile = self._projects_dir() / project / "project.json"
            if not pfile.exists():
                return f"ERROR: project '{project}' not found"
            with open(pfile, encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("subprojects", {})
            if name in data["subprojects"]:
                return f"ERROR: subproject '{name}' already exists"
            data["subprojects"][name] = {"created_at": datetime.now().isoformat()}
            with open(pfile, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return f"OK: added subproject '{name}' to '{project}'"
        except Exception as e:
            return f"ERROR: {e}"

    @command(dtype_in=str, dtype_out=str, display_level=DispLevel.OPERATOR)
    def create_measurement(self, value: str):
        try:
            payload = self._try_json(value)
            if not isinstance(payload, dict):
                return "ERROR: provide JSON {'project':..., 'name':..., 'info':{...}}"
            project = str(payload.get("project", "")).strip()
            name = str(payload.get("name", "")).strip()
            info = payload.get("info", {})
            if not project or not name:
                return "ERROR: 'project' and 'name' required"
            pfile = self._projects_dir() / project / "project.json"
            if not pfile.exists():
                return f"ERROR: project '{project}' not found"
            with open(pfile, encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("measurements", {})
            if name in data["measurements"]:
                return f"ERROR: measurement '{name}' already exists"
            data["measurements"][name] = {
                "created_at": datetime.now().isoformat(),
                "info": info,
                "data": [],
            }
            with open(pfile, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return f"OK: created measurement '{name}' in '{project}'"
        except Exception as e:
            return f"ERROR: {e}"

    @command(dtype_in=str, dtype_out=str, display_level=DispLevel.OPERATOR)
    def edit_measurement_info(self, value: str):
        try:
            payload = self._try_json(value)
            if not isinstance(payload, dict):
                return "ERROR: provide JSON {'project':..., 'name':..., 'set':{...}}"
            project = str(payload.get("project", "")).strip()
            name = str(payload.get("name", "")).strip()
            to_set = payload.get("set", {})
            if not project or not name:
                return "ERROR: 'project' and 'name' required"
            pfile = self._projects_dir() / project / "project.json"
            if not pfile.exists():
                return f"ERROR: project '{project}' not found"
            with open(pfile, encoding="utf-8") as f:
                data = json.load(f)
            if name not in data.get("measurements", {}):
                return f"ERROR: measurement '{name}' not found"
            data["measurements"][name].setdefault("info", {}).update(to_set)
            with open(pfile, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return f"OK: edited measurement '{name}' in '{project}'"
        except Exception as e:
            return f"ERROR: {e}"

    @command(dtype_in=str, dtype_out=str, display_level=DispLevel.OPERATOR)
    def add_data_measurement(self, value: str):
        try:
            payload = self._try_json(value)
            if not isinstance(payload, dict):
                return "ERROR: provide JSON {'project':..., 'name':..., 'data':{...}}"
            project = str(payload.get("project", "")).strip()
            name = str(payload.get("name", "")).strip()
            data_item = payload.get("data", {})
            if not project or not name:
                return "ERROR: 'project' and 'name' required"
            pfile = self._projects_dir() / project / "project.json"
            if not pfile.exists():
                return f"ERROR: project '{project}' not found"
            with open(pfile, encoding="utf-8") as f:
                data = json.load(f)
            if name not in data.get("measurements", {}):
                return f"ERROR: measurement '{name}' not found"
            data["measurements"][name].setdefault("data", []).append(data_item)
            with open(pfile, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return f"OK: added data to measurement '{name}' in '{project}'"
        except Exception as e:
            return f"ERROR: {e}"

    @command(dtype_in=str, dtype_out=str, display_level=DispLevel.OPERATOR)
    def edit_measurement_data(self, value: str):
        try:
            payload = self._try_json(value)
            if not isinstance(payload, dict):
                return "ERROR: provide JSON {'project':..., 'name':..., 'index': i, 'set':{...}}"
            project = str(payload.get("project", "")).strip()
            name = str(payload.get("name", "")).strip()
            index = int(payload.get("index", -1))
            to_set = payload.get("set", {})
            if not project or not name or index < 0:
                return "ERROR: 'project', 'name', and non-negative 'index' required"
            pfile = self._projects_dir() / project / "project.json"
            if not pfile.exists():
                return f"ERROR: project '{project}' not found"
            with open(pfile, encoding="utf-8") as f:
                data = json.load(f)
            if name not in data.get("measurements", {}):
                return f"ERROR: measurement '{name}' not found"
            items = data["measurements"][name].setdefault("data", [])
            if index >= len(items):
                return f"ERROR: index {index} out of range"
            if isinstance(items[index], dict) and isinstance(to_set, dict):
                items[index].update(to_set)
            else:
                items[index] = to_set
            with open(pfile, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return (
                f"OK: edited data item {index} in measurement '{name}' of '{project}'"
            )
        except Exception as e:
            return f"ERROR: {e}"


if __name__ == "__main__":
    DS_Archive.run_server()
