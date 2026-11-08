"""Implementation for Order and related operations."""


def _bind_archive_device_parts_order(api):
    """Bind implementation to the owning module and its runtime state."""

    class Order:
        order_param: api.List[str]
        timestamp: int
        started: bool = False
        order_done: bool = False
        ready_to_delete: bool = False
        order_res: str = ""

    Order.__module__ = api.__name__
    Order.__qualname__ = "Order"

    class H5_container:
        file_path: api.Path
        parent: object
        close_thread: api.Thread = None
        h5_file: api.h5py.File = None
        lock: bool = False
        close_time: int = 5

        def __post_init__(self):
            self.open()
            self._structure = {}
            self._prev_size = self.file_path.stat().st_size
            self.close_thread = api.Thread(target=self.closing)
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
                self.h5_file = api.h5py.File(str(self.file_path), "a")
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
                    if isinstance(obj[key], api.h5py.Dataset):
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
        def devices_list(self) -> api.List[str]:
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
                api.sleep(self.close_time)
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

    H5_container.__module__ = api.__name__
    H5_container.__qualname__ = "H5_container"

    def _archive_to_payload_dict(data: api.ArchiveData) -> dict:
        if isinstance(data.data, api.Scalar):
            payload_data = {
                "kind": "Scalar",
                "value": data.data.value,
                "dtype": data.data.dtype,
            }
        elif isinstance(data.data, api.Array):
            payload_data = {
                "kind": "Array",
                "value": api.base64.b64encode(data.data.value).decode("ascii"),
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

    _archive_to_payload_dict.__module__ = api.__name__
    _archive_to_payload_dict.__qualname__ = "_archive_to_payload_dict"

    def _payload_dict_to_archive(d: dict) -> api.ArchiveData:
        if not isinstance(d, dict) or d.get("kind") != "ArchiveData":
            raise ValueError("Invalid payload: not an ArchiveData dict")
        pdata = d.get("data", {})
        if pdata.get("kind") == "Scalar":
            data_field = api.Scalar(value=float(pdata["value"]), dtype=str(pdata["dtype"]))
        elif pdata.get("kind") == "Array":
            raw = (
                api.base64.b64decode(pdata["value"])
                if isinstance(pdata.get("value"), str)
                else pdata.get("value", b"")
            )
            shape = tuple(pdata.get("shape", []))
            dtype = str(pdata.get("dtype", "float"))
            data_field = api.Array(value=raw, shape=shape, dtype=dtype)
        else:
            raise ValueError("Invalid payload: unknown data.kind")
        return api.ArchiveData(
            tango_device=str(d["tango_device"]),
            data_timestamp=float(d["data_timestamp"]),
            dataset_name=str(d["dataset_name"]),
            data=data_field,
        )

    _payload_dict_to_archive.__module__ = api.__name__
    _payload_dict_to_archive.__qualname__ = "_payload_dict_to_archive"

    def encode_archive_payload(data: api.ArchiveData) -> str:
        packed = api.msgpack.packb(api._archive_to_payload_dict(data), use_bin_type=True)
        compressed = api.zlib.compress(packed)
        return api.B64_PREFIX + api.base64.b64encode(compressed).decode("ascii")

    encode_archive_payload.__module__ = api.__name__
    encode_archive_payload.__qualname__ = "encode_archive_payload"

    def decode_archive_payload(data_string: str) -> api.ArchiveData:
        # New format: b64:<base64(zlib(msgpack(dict)))>
        if isinstance(data_string, bytes):
            data_string = data_string.decode("utf-8")
        if str(data_string).startswith(api.B64_PREFIX):
            b64 = data_string[len(api.B64_PREFIX) :]
            compressed = api.base64.b64decode(b64)
            unpacked = api.msgpack.unpackb(api.zlib.decompress(compressed), raw=False)
            return api._payload_dict_to_archive(unpacked)
        # Legacy format: str(bytes(zlib(msgpack(str(dataclass))))) -> eval
        try:
            data_bytes = eval(data_string)
            data = api.zlib.decompress(data_bytes)
            unpacked = api.msgpack.unpackb(data, strict_map_key=False)
            # unpacked here is a string representation of dataclass, legacy path
            return eval(unpacked)
        except Exception as e:
            raise ValueError(f"Failed to decode payload: {e}")

    decode_archive_payload.__module__ = api.__name__
    decode_archive_payload.__qualname__ = "decode_archive_payload"

    return {
        "Order": Order,
        "H5_container": H5_container,
        "_archive_to_payload_dict": _archive_to_payload_dict,
        "_payload_dict_to_archive": _payload_dict_to_archive,
        "encode_archive_payload": encode_archive_payload,
        "decode_archive_payload": decode_archive_payload,
    }
