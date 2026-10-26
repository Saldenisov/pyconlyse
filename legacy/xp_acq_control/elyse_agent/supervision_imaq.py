"""NI1409 raw-frame owner, NI-IMAQ C API (not IMAQdx); Python 3.4.

Import/construction performs no driver or filesystem I/O. Explicit Initialize
alone loads the installed 32-bit NI-IMAQ library and opens img0. Prototype and
attribute constants come from NI's installed niimaq.h. Raw U8 frames precede
the legacy Vision interlace/BCG/profile pipeline; they are not C12NI1409's
String publication. No reset, reconnect or camera retry is performed.
"""
import base64
import datetime
import math
import time

from .supervision_cards import SupervisionCardError

IMG_BASE = 0x3ff60000
ATTR_CHANNEL = IMG_BASE + 0x0006
ATTR_BYTESPERPIXEL = IMG_BASE + 0x0067
ATTR_FRAMEWAIT_MSEC = IMG_BASE + 0x007d
ATTR_BLACK_REF_VOLT = IMG_BASE + 0x00bc
ATTR_WHITE_REF_VOLT = IMG_BASE + 0x00bd
ATTR_ROWPIXELS = IMG_BASE + 0x00c1
ATTR_IMAGE_TYPE = IMG_BASE + 0x00d8
ATTR_ROI_WIDTH = IMG_BASE + 0x01a6
ATTR_ROI_HEIGHT = IMG_BASE + 0x01a7
MAX_FRAME_BYTES = 524288
ROOT_INIT_DIAGRAM = "12058"
SOURCE_CAMERA_NODES = dict(init="18953", properties="15292", setup="18912",
                           acquire="15740", dispose="22899", close="22923")


def source_video_configuration():
    """Saved original front-panel defaults, not a current VI readback.

    FPHb UID15301 DefaultData=3FECCCCCCCCCCCCD (White), UID19202
    3FB999999999999A (Black), UID19558 U16=0002 (channel).
    """
    return dict(channel=2, white_ref_volt=.9, black_ref_volt=.1)


class IMAQNativeError(RuntimeError):
    def __init__(self, function, code):
        self.code = int(code)
        RuntimeError.__init__(self, "{0}: NI-IMAQ status {1}".format(function, code))


class CtypesIMAQ(object):
    """Deferred installed-library binding. No arbitrary DLL path from requests."""
    def __init__(self):
        self.stdcall = self.cdecl = self.ctypes = None

    def _load(self):
        if self.stdcall is not None:
            return
        import ctypes
        import os
        if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 4:
            raise RuntimeError("NI1409 worker requires 32-bit Windows Python")
        stdcall, cdecl = ctypes.WinDLL("imaq.dll"), ctypes.CDLL("imaq.dll")
        u32, ptr = ctypes.c_uint32, ctypes.c_void_p
        signatures = {
            "imgInterfaceOpen": [ctypes.c_char_p, ctypes.POINTER(u32)],
            "imgSessionOpen": [u32, ctypes.POINTER(u32)],
            "imgClose": [u32, u32], "imgGrabSetup": [u32, u32],
            "imgGrab": [u32, ctypes.POINTER(ptr), u32],
            "imgSessionStopAcquisition": [u32],
            "imgGetAttribute": [u32, u32, ptr],
            "imgSessionGetBufferSize": [u32, ctypes.POINTER(u32)],
        }
        for name, arguments in signatures.items():
            function = getattr(stdcall, name)
            function.argtypes, function.restype = arguments, ctypes.c_int32
        # NI declares this variadic function __cdecl, unlike the others.
        setter = cdecl.imgSetAttribute2
        setter.argtypes, setter.restype = [u32, u32], ctypes.c_int32
        self.stdcall, self.cdecl, self.ctypes = stdcall, cdecl, ctypes

    def _call(self, name, *arguments):
        self._load()
        code = getattr(self.stdcall, name)(*arguments)
        if code < 0:
            raise IMAQNativeError(name, code)
        return code

    def open_interface(self, name):
        self._load()
        result = self.ctypes.c_uint32()
        self._call("imgInterfaceOpen", name.encode("ascii"), self.ctypes.byref(result))
        return result.value

    def open_session(self, interface):
        result = self.ctypes.c_uint32()
        self._call("imgSessionOpen", interface, self.ctypes.byref(result))
        return result.value

    def set_attribute(self, handle, attribute, value):
        self._load()
        encoded = self.ctypes.c_double(value) if type(value) is float else self.ctypes.c_uint32(value)
        code = self.cdecl.imgSetAttribute2(handle, attribute, encoded)
        if code < 0:
            raise IMAQNativeError("imgSetAttribute2", code)

    def get_u32(self, handle, attribute):
        value = self.ctypes.c_uint32()
        self._call("imgGetAttribute", handle, attribute, self.ctypes.byref(value))
        return value.value

    def grab_setup(self, session):
        self._call("imgGrabSetup", session, 1)

    def grab(self, session, maximum):
        width = self.get_u32(session, ATTR_ROI_WIDTH)
        height = self.get_u32(session, ATTR_ROI_HEIGHT)
        rowpixels = self.get_u32(session, ATTR_ROWPIXELS)
        pixel_bytes = self.get_u32(session, ATTR_BYTESPERPIXEL)
        image_type = self.get_u32(session, ATTR_IMAGE_TYPE)
        size = self.ctypes.c_uint32()
        self._call("imgSessionGetBufferSize", session, self.ctypes.byref(size))
        if (not width or not height or pixel_bytes != 1 or image_type != 0
                or rowpixels < width or width * height > maximum
                or rowpixels * height > size.value or size.value > 4 * maximum):
            raise ValueError("Bounded U8 NI1409 geometry required before copying a buffer")
        pointer = self.ctypes.c_void_p()
        self._call("imgGrab", session, self.ctypes.byref(pointer), 1)
        if not pointer.value:
            raise ValueError("NI-IMAQ returned a null frame buffer")
        # Drop native row padding, retaining raw row order. The same owner is
        # the only caller and copies before its next grab; no borrowed pointer
        # crosses an IPC boundary.
        data = b"".join(self.ctypes.string_at(pointer.value + row * rowpixels, width)
                        for row in range(height))
        return dict(width=width, height=height, data=data, pixel_type="U8")

    def stop(self, session):
        self._call("imgSessionStopAcquisition", session)

    def close(self, handle):
        self._call("imgClose", handle, 1)


class SupervisionVideoCard(object):
    def __init__(self, driver=None, max_frame_bytes=MAX_FRAME_BYTES, timeout_ms=500):
        if type(max_frame_bytes) is not int or not 1 <= max_frame_bytes <= MAX_FRAME_BYTES:
            raise ValueError("Explicit bounded raw-frame size required")
        if type(timeout_ms) is not int or not 10 <= timeout_ms <= 2000:
            raise ValueError("Bounded camera wait required")
        self.driver = driver if driver is not None else CtypesIMAQ()
        self.maximum, self.timeout_ms = max_frame_bytes, timeout_ms
        self.interface = self.session = None
        self.creation_uncertain = False
        self.initialized = False
        self.configuration = None
        self.sequence = 0
        self.last_error = ""

    @property
    def resource_count(self):
        return int(self.interface is not None) + int(self.session is not None) + int(self.creation_uncertain)

    def prepare_isolated_dependencies(self):
        """Resolve NI-IMAQ DLL symbols only; never open img0 or a session."""
        if isinstance(self.driver, CtypesIMAQ):
            self.driver._load()

    def initialize(self, configuration, operator_confirmed=False, resources_released_confirmed=False):
        if operator_confirmed is not True or resources_released_confirmed is not True:
            raise ValueError("Explicit local VI release and video initialization confirmation required")
        if self.resource_count or self.initialized:
            raise RuntimeError("Retained camera owner cannot be replaced")
        if (type(configuration) is not dict
                or set(configuration) != {"channel", "white_ref_volt", "black_ref_volt"}
                or type(configuration["channel"]) is not int or not 0 <= configuration["channel"] <= 3
                or any(type(configuration[k]) not in (int, float) or not math.isfinite(configuration[k])
                       for k in ("white_ref_volt", "black_ref_volt"))):
            raise ValueError("Explicit source channel and both finite threshold voltages required")
        self.configuration = dict(configuration)
        try:
            self.creation_uncertain = True
            self.interface = self.driver.open_interface("img0")
            self.creation_uncertain = False
            self.creation_uncertain = True
            self.session = self.driver.open_session(self.interface)
            self.creation_uncertain = False
            self.driver.set_attribute(self.session, ATTR_WHITE_REF_VOLT, float(configuration["white_ref_volt"]))
            self.driver.set_attribute(self.session, ATTR_BLACK_REF_VOLT, float(configuration["black_ref_volt"]))
            # Channel is an explicit Grab Setup input in the source, not the
            # selector event's NewVal. This C API adapter writes that same local
            # configuration before its explicit high-level Grab Setup call.
            self.driver.set_attribute(self.session, ATTR_CHANNEL, configuration["channel"])
            self.driver.set_attribute(self.session, ATTR_FRAMEWAIT_MSEC, self.timeout_ms)
            self.driver.grab_setup(self.session)
        except Exception as error:
            self.last_error = type(error).__name__ + ": " + str(error)
            raise SupervisionCardError("NI1409 initialization failed: " + str(error), self)
        self.initialized = True
        return self.snapshot()

    def snapshot(self):
        return dict(card="NI1409", interface="img0", resource_count=self.resource_count,
            initialized=self.initialized, creation_uncertain=self.creation_uncertain,
            configuration=dict(self.configuration or {}), sequence=self.sequence,
            last_error=self.last_error, raw_frames_only=True, C12NI1409_contains_pixels=False,
            hardware_acknowledged=False, automatic_restart=False)

    def read_frame(self):
        if not self.initialized or self.session is None:
            raise RuntimeError("Current initialized NI1409 owner required")
        started = time.monotonic()
        value = self.driver.grab(self.session, self.maximum)
        if (type(value) is not dict or set(value) != {"width", "height", "data", "pixel_type"}
                or any(type(value[k]) is not int or value[k] <= 0 for k in ("width", "height"))
                or value["pixel_type"] != "U8" or type(value["data"]) is not bytes
                or len(value["data"]) != value["width"] * value["height"]
                or len(value["data"]) > self.maximum):
            raise ValueError("Invalid bounded raw U8 frame; no stale frame fallback")
        self.sequence += 1
        return dict(source="python_supervision_ni1409", simulated=False,
            sequence=self.sequence, sequence_interpretation="software grab observation, not hardware frame counter",
            observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            sample_elapsed_seconds=time.monotonic() - started,
            width=value["width"], height=value["height"], pixel_type="U8",
            encoding="base64_raw_row_major", data=base64.b64encode(value["data"]).decode("ascii"),
            channel=self.configuration["channel"],
            processing="raw_grab_before_legacy_interlace_bcg_profiles",
            hardware_acknowledged=False)

    def close(self):
        self.initialized = False
        failures = []
        if self.session is not None:
            try:
                self.driver.stop(self.session)
            except Exception as error:
                failures.append("stop: " + str(error))
            try:
                self.driver.close(self.session)
            except Exception as error:
                failures.append("close session: " + str(error))
            else:
                self.session = None
        # A still-retained child session must not be invalidated indirectly
        # through freeResources on its parent interface.
        if self.interface is not None and self.session is None:
            try:
                self.driver.close(self.interface)
            except Exception as error:
                failures.append("close interface: " + str(error))
            else:
                self.interface = None
        if failures or self.creation_uncertain:
            raise SupervisionCardError("NI1409 cleanup incomplete: " + "; ".join(failures), self)
