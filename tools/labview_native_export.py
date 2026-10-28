"""Export an audited, stopped VI using LabVIEW's own SaveForPrevious method.

No RSRC writer, VI execution, front-panel action, driver call or source save.
Python 3.4 compatible. Native automation requires Windows and pywin32.
Dependency closure and the actual output version require separate verification.
"""

import argparse
import hashlib
import json
import ntpath
from pathlib import Path

try:
    from tools.verify_labview_sync_native12_package import vi_header
except ImportError:  # Direct invocation from the tools directory.
    from verify_labview_sync_native12_package import vi_header


APPLICATION_DIRECTORY = r"C:\Program Files (x86)\National Instruments\LabVIEW 2020"
CLSID = "{9A872070-0A06-11D1-90B7-00A024CE2744}"
VERSION = "12.0"


def read_bytes(path):
    with path.open("rb") as stream:
        return stream.read()


def digest(path):
    return hashlib.sha256(read_bytes(path)).hexdigest()


class NativeApplication:
    """Use explicit native method dispatch; do not use stale makepy wrappers."""

    def __init__(self):
        import pythoncom
        import pywintypes
        from win32com.client import dynamic

        self.pythoncom = pythoncom
        self.dynamic = dynamic
        dispatch = pythoncom.CoCreateInstance(
            pywintypes.IID(CLSID), None,
            pythoncom.CLSCTX_LOCAL_SERVER | 0x40000,  # ACTIVATE_32_BIT_SERVER
            pythoncom.IID_IDispatch,
        )
        self.app = dynamic.Dispatch(dispatch)

    def identity(self):
        return {
            "directory": str(self.app.ApplicationDirectory),
            "version": str(self.app.Version),
            "process_id": int(self.app._ProcessID),
        }

    def open_vi(self, source):
        # RunOnOpen must already have been excluded by the source qualification.
        ref = self.app.GetVIReference(str(source), "", False, 0)
        return self.dynamic.Dispatch(ref._oleobj_)

    def state(self, vi):
        return {
            "path": str(vi.Path),
            "execution": int(vi.ExecState),
            "vi_modifications": int(vi.VIModificationBitSet),
            "fp_modifications": int(vi.FPModificationBitSet),
            "bd_modifications": int(vi.BDModificationBitSet),
        }

    def export(self, vi, destination):
        pc = self.pythoncom
        # The installed x86 type library declares DISPID1024 and these types.
        # Dynamic attribute lookup can accidentally invoke this method with no
        # arguments; explicit InvokeTypes also avoids broken makepy wrappers.
        return vi._oleobj_.InvokeTypes(
            1024, 0, pc.DISPATCH_METHOD, (pc.VT_VOID, 0),
            ((pc.VT_BSTR, 1), (pc.VT_BYREF | pc.VT_BSTR, 18),
             (pc.VT_BSTR, 17)),
            str(destination), "", VERSION,
        )


def require_stopped_clean(state, source):
    if ntpath.normcase(state["path"]) != ntpath.normcase(str(source)):
        raise ValueError("LabVIEW resolved a different source VI")
    if state["execution"] != 1:
        raise ValueError("Source VI is not in LabVIEW's idle state")
    if any(state[key] for key in (
        "vi_modifications", "fp_modifications", "bd_modifications"
    )):
        raise ValueError("Source VI has unsaved in-memory modifications")


def export_native(source, destination, expected_sha256, app_factory=None):
    source, destination = Path(source), Path(destination)
    if not source.is_absolute() or not destination.is_absolute():
        raise ValueError("Source and destination must be absolute paths")
    if source.suffix.lower() != ".vi" or destination.suffix.lower() != ".vi":
        raise ValueError("Source and destination must be VI files")
    if not source.is_file() or not destination.parent.is_dir():
        raise ValueError("Source file and destination parent must exist")
    if destination.exists():
        raise ValueError("Destination already exists; native export cannot overwrite")
    expected_sha256 = expected_sha256.lower()
    if (len(expected_sha256) != 64 or
            any(c not in "0123456789abcdef" for c in expected_sha256)):
        raise ValueError("Expected SHA256 must contain 64 hexadecimal characters")
    if digest(source) != expected_sha256:
        raise ValueError("Source bytes do not match the audited SHA256")
    source_header = vi_header(read_bytes(source))
    if source_header["RunOnOpen"] or source_header["major"] != 20:
        raise ValueError("Expected native20 source with RunOnOpen disabled")

    app = (app_factory or NativeApplication)()
    identity = app.identity()
    if ntpath.normcase(identity["directory"]) != ntpath.normcase(APPLICATION_DIRECTORY):
        raise ValueError("Expected native LabVIEW 2020 x86 application")
    if not identity["version"].startswith("20.0"):
        raise ValueError("Unexpected LabVIEW application version")
    vi = app.open_vi(source)
    before = app.state(vi)
    require_stopped_clean(before, source)
    if digest(source) != expected_sha256 or destination.exists():
        raise ValueError("Source or destination changed before native export")
    warnings = app.export(vi, destination)
    after = app.state(vi)
    require_stopped_clean(after, source)
    if digest(source) != expected_sha256:
        raise ValueError("Source bytes changed during native export")
    if not destination.is_file() or not destination.stat().st_size:
        raise ValueError("Native export did not produce a nonempty file")
    output_header = vi_header(read_bytes(destination))
    if output_header["RunOnOpen"] or output_header["major"] != 12:
        raise ValueError("Native export must produce native12 with RunOnOpen disabled")
    return {
        "source": str(source), "source_sha256": expected_sha256,
        "destination": str(destination), "bytes": destination.stat().st_size,
        "sha256": digest(destination), "requested_version": VERSION,
        "native_warnings": warnings, "application": identity,
        "before": before, "after": after, "source_unchanged": True,
        "Run": False, "SaveInstrument": False, "RSRC_writer": False,
        "source_header": source_header, "output_header": output_header,
        "output_version_verified": True,
        "output_version_and_dependencies_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args()
    report = export_native(args.source, args.destination, args.expect_sha256)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
