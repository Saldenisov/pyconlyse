#!/usr/bin/env python

import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# Ensure repo root on sys.path for absolute imports
repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Provide minimal mocks for tango and taurus to avoid heavy dependencies during this test
import types

if "tango" not in sys.modules:
    tango = types.ModuleType("tango")

    class AttrWriteType:
        READ = 0
        READ_WRITE = 1

    class DevState:
        ON = 1
        OFF = 0
        FAULT = 3
        STANDBY = 4
        MOVING = 5
        RUNNING = 6
        INIT = 7

    class DispLevel:
        OPERATOR = 0

    server = types.ModuleType("tango.server")

    def _identity_decorator(*args, **kwargs):
        def deco(f):
            return f

        return deco

    def device_property(**kwargs):
        # Return a simple placeholder; not used in this test
        return 0

    class Device:
        def init_device(self):
            pass

        def info_stream(self, *args, **kwargs):
            pass

        def error_stream(self, *args, **kwargs):
            pass

    server.attribute = _identity_decorator
    server.command = _identity_decorator
    server.device_property = device_property
    server.pipe = _identity_decorator
    server.Device = Device
    tango.AttrWriteType = AttrWriteType
    tango.DevState = DevState
    tango.DispLevel = DispLevel
    sys.modules["tango"] = tango
    sys.modules["tango.server"] = server

if "taurus" not in sys.modules:
    taurus = types.ModuleType("taurus")

    class MockDevice:
        def __init__(self, *args, **kwargs):
            self.state = 0

    taurus.Device = MockDevice
    sys.modules["taurus"] = taurus

from DeviceServers.data.archive.DS_Archive import (
    ArchiveData,
    Array,
    H5_container,
    Scalar,
    decode_archive_payload,
    encode_archive_payload,
)


def write_archive_sample(container: H5_container, data: ArchiveData):
    container.open(lock=True)
    try:
        # Mirror DS_Archive.archive_it core logic (without Tango)
        if isinstance(data.data, Scalar):
            data_to_archive = np.array([data.data.value])
        elif isinstance(data.data, Array):
            data_to_archive = np.frombuffer(
                data.data.value, dtype=data.data.dtype
            ).reshape(data.data.shape)
        else:
            raise ValueError("Unsupported data type")

        ts = float(data.data_timestamp)
        dt = datetime.fromtimestamp(ts)
        date_as_str = dt.date().__str__()
        dataset_name_h5 = f"{date_as_str}/{data.tango_device}/{data.dataset_name}"
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
        else:
            raise ValueError("Unsupported array rank")

        container.dataset_update(
            dataset_name_h5,
            shape=shape,
            maxshape=maxshape,
            dtype=np.dtype(data.data.dtype),
            data=data_to_archive,
        )
        ts_array = np.array([ts], dtype="float")
        container.dataset_update(
            f"{dataset_name_h5}_timestamp",
            (ts_array.shape[0],),
            (None,),
            ts_array.dtype,
            ts_array,
        )
        return dataset_name_h5
    finally:
        container.lock = False


def get_object_timestamps_like(container: H5_container, dataset_name: str):
    container.open(True)
    timestamps_objs = container.get_object(f"{dataset_name}_timestamp")
    spans = []
    for item_ts in timestamps_objs:
        if len(item_ts) > 0:
            spans.append((float(item_ts[0]), float(item_ts[-1]), len(item_ts)))
    if spans:
        mins = [s[0] for s in spans]
        maxs = [s[1] for s in spans]
        lens = [s[2] for s in spans]
        res = [min(mins), max(maxs), int(np.sum(lens))]
    else:
        res = [time.time(), time.time(), 0]
    container.lock = False
    return res


def main():
    root = Path(__file__).resolve().parent
    test_dir = root / "_tmp_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    h5_path = test_dir / "test_archive.hdf5"

    cont = H5_container(file_path=h5_path, parent=None, close_time=999)

    # Scalar sample
    ad = ArchiveData(
        tango_device="elyse/test/device",
        dataset_name="value",
        data_timestamp=time.time(),
        data=Scalar(3.14, "float"),
    )

    payload = encode_archive_payload(ad)
    decoded = decode_archive_payload(payload)

    ds_name = write_archive_sample(cont, decoded)

    # Timestamps summary
    summary = get_object_timestamps_like(cont, ds_name)
    print("Dataset:", ds_name)
    print("Timestamps summary:", summary)


if __name__ == "__main__":
    main()
