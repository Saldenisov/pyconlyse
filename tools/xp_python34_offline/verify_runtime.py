# -*- coding: utf-8 -*-
"""Read-only validation of Python, nidaqmx, driver, and detected devices."""

from __future__ import print_function

import os
import struct
import sys
import traceback


REPORT_PATH = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "verification-report.txt"
)


def safe_value(obj, name):
    try:
        return getattr(obj, name)
    except Exception as exc:
        return "<unavailable: %s>" % exc


def physical_channel_names(collection):
    try:
        return [channel.name for channel in collection]
    except Exception as exc:
        return ["<unavailable: %s>" % exc]


def write_report(stream):
    import nidaqmx
    import numpy
    import six
    from nidaqmx.system import System

    print("Python=%s" % sys.version.replace("\n", " "), file=stream)
    print("PythonBits=%s" % (struct.calcsize("P") * 8), file=stream)
    print("numpy=%s" % numpy.__version__, file=stream)
    print("six=%s" % six.__version__, file=stream)
    print(
        "nidaqmx=%s" % getattr(nidaqmx, "__version__", "0.5.7"),
        file=stream,
    )

    system = System.local()
    version = system.driver_version
    print(
        "DAQmxDriver=%s.%s.%s"
        % (version.major_version, version.minor_version, version.update_version),
        file=stream,
    )

    devices = list(system.devices)
    print("DeviceCount=%s" % len(devices), file=stream)
    for device in devices:
        print("DEVICE %s" % device.name, file=stream)
        print("  product_type=%s" % safe_value(device, "product_type"), file=stream)
        print("  serial_num=%s" % safe_value(device, "serial_num"), file=stream)
        print(
            "  ai=%s" % physical_channel_names(device.ai_physical_chans),
            file=stream,
        )
        print(
            "  ao=%s" % physical_channel_names(device.ao_physical_chans),
            file=stream,
        )
        print(
            "  di=%s" % physical_channel_names(device.di_lines),
            file=stream,
        )
        print(
            "  do=%s" % physical_channel_names(device.do_lines),
            file=stream,
        )
        print(
            "  ci=%s" % physical_channel_names(device.ci_physical_chans),
            file=stream,
        )
        print(
            "  co=%s" % physical_channel_names(device.co_physical_chans),
            file=stream,
        )


def main():
    with open(REPORT_PATH, "w") as stream:
        try:
            write_report(stream)
            print("VERIFICATION_OK", file=stream)
        except Exception:
            traceback.print_exc(file=stream)
            print("VERIFICATION_FAILED", file=stream)
            raise


if __name__ == "__main__":
    main()
