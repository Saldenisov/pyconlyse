"""Write native HPD-TA calibration tables without changing any frame bytes."""
import hashlib
import os
from pathlib import Path
import re
import struct
from uuid import uuid4

import numpy as np

from utilities.dataio.hamamatsu_file_opener import HamamatsuFileOpener


_TABLE_REFERENCE = re.compile(rb'(=\"#)(\d{7})((?:,\d{4})?\")')
_PIXEL_X = re.compile(rb'ScalingXType=1,ScalingXScale=[^,]+,ScalingXUnit="(?:|No unit|pixel)",ScalingXScalingFile="Other"')


def _signature(info):
    return info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino


def _copy_frames(source, target=None):
    digest = hashlib.sha256()
    while block := source.read(1024 * 1024):
        digest.update(block)
        if target is not None:
            target.write(block)
    return digest.digest()


def spectral_calibration_metadata(header):
    match = re.search(
        r'(?m)^\[PyConlyseSpectral\],ID="([A-Za-z0-9_.-]+)",ValidColumns="(\d+),(\d+)"',
        header,
    )
    return (match[1], (int(match[2]), int(match[3]))) if match else None


def relative_delays(values):
    """Translate the first recorded detector row to zero without flipping the axis."""
    axis = np.asarray(values, dtype=float)
    if not axis.size or axis[0] == 0:
        return axis
    return (axis - axis[0]).astype("<f4")


def time_origin_metadata(header):
    match = re.search(r'(?m)^\[PyConlyseTime\],OriginalFirst="([-+eE.0-9]+)"', header)
    return float(match[1]) if match else None


def embed_native_axes(path, wavelengths=None, *, calibration_id=None, valid_columns=None,
                      replace_existing=False, zero_time=False):
    """Write axes to a native IMG or HIS with the original frame payload intact."""
    path = Path(path)
    if path.suffix.lower() not in {'.his', '.img'} or path.is_symlink():
        raise ValueError("Expected a native IMG or HIS file")

    original = path.stat()
    info = HamamatsuFileOpener().read_critical_info(path)
    axis = None if wavelengths is None else np.asarray(wavelengths, dtype='<f4')
    if axis is not None and (axis.shape != (info.wavelengths_length,) or len(axis) < 2
            or not np.isfinite(axis).all()
            or not (np.all(np.diff(axis) > 0) or np.all(np.diff(axis) < 0))):
        raise ValueError("Invalid wavelength table for detector width")
    metadata = b""
    if valid_columns is not None:
        low, high = valid_columns
        if (not isinstance(calibration_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", calibration_id)
                or any(type(column) is not int for column in (low, high))
                or axis is None or not 0 <= low < high < len(axis)):
            raise ValueError("Invalid native calibration identity or measured columns")
        metadata = (f'\r\n[PyConlyseSpectral],ID="{calibration_id}",ValidColumns="{low},{high}"\r\n'
                    .encode("ascii"))
    parsed_metadata = spectral_calibration_metadata(info.header)
    if axis is not None and parsed_metadata and parsed_metadata != (calibration_id, valid_columns):
        raise ValueError("File already bears different PyConlyse calibration metadata")
    update_x = axis is not None
    if axis is not None and info.scaling_xunit == 'nm':
        matches_axis = np.array_equal(info.wavelengths, axis)
        if not matches_axis and not replace_existing:
            raise ValueError("File already has a different wavelength calibration")
        update_x = not matches_axis or bool(metadata and not parsed_metadata)
    elif axis is not None and info.file_type != 'Other':
        raise ValueError("Unsupported native spectral header; original retained")

    if not update_x:
        metadata = b""
    old_delays = np.asarray(info.timedelays)
    delays = relative_delays(old_delays) if zero_time else old_delays
    update_y = bool(zero_time and old_delays.size and old_delays[0] != 0)
    if update_y:
        if (not np.isfinite(delays).all()
                or not (np.all(np.diff(delays) > 0) or np.all(np.diff(delays) < 0))):
            raise ValueError("Invalid native time calibration; original retained")
        metadata += f'\r\n[PyConlyseTime],OriginalFirst="{float(old_delays[0]):.17g}"\r\n'.encode("ascii")
    if not update_x and not update_y:
        return axis

    # A sibling inherits the experiment folder's permissions on Windows.
    staged = path.with_name(f'.hamamatsu-calibration-{uuid4().hex}{path.suffix.lower()}')
    try:
        with path.open('rb') as source, staged.open('xb') as target:
            fixed = bytearray(source.read(64))
            comment = source.read(info.data_pos - 64)
            count = struct.unpack_from('<H', fixed, 14)[0] or 1
            kind = struct.unpack_from('<H', fixed, 12)[0]
            frame_size = info.wavelengths_length * info.timedelays_length * info.bytes_per_point
            if (fixed[:2] != b'IM' or kind not in (0, 2, 3)
                    or (path.suffix.lower() == ".img" and count != 1)
                    or count * (64 + frame_size) + len(comment) != original.st_size):
                raise ValueError("Unsupported or incomplete native image data")
            # The first comment holds all calibration tables. Identify the
            # binary boundary by native absolute offsets before changing text.
            refs = list(_TABLE_REFERENCE.finditer(comment))
            starts = [int(ref[2]) for ref in refs if ref.start() + 64 < int(ref[2]) < info.data_pos]
            boundary = min(starts, default=info.data_pos) - 64
            text, tables = comment[:boundary], comment[boundary:]
            if update_y:
                y_ref = re.search(rb'ScalingYScalingFile="#(\d{7})(?:,\d{4})?"', text)
                if y_ref is None or not 64 + boundary <= int(y_ref[1]) <= info.data_pos - delays.nbytes:
                    raise ValueError("No supported native Y table; original HIS retained")
                at = int(y_ref[1]) - 64 - boundary
                tables = tables[:at] + delays.tobytes() + tables[at + delays.nbytes:]
            x_table = b""
            shift = len(metadata)
            template = b'ScalingXType=2,ScalingXScale=1,ScalingXUnit="nm",ScalingXScalingFile="#%07d,%04d"'
            if update_x:
                calibrated_x = re.compile(
                    rb'ScalingXType=2,ScalingXScale=[^,]+,ScalingXUnit="nm",ScalingXScalingFile="#\d{7},\d{4}"'
                )
                field_pattern = calibrated_x if info.scaling_xunit == "nm" else _PIXEL_X
                matches = list(field_pattern.finditer(text))
                if len(matches) != 1:
                    raise ValueError("Expected one supported X field; original HIS retained")
                shift += len(template % (0, len(axis))) - len(matches[0][0])
                x_table = axis.tobytes()
            for ref in _TABLE_REFERENCE.finditer(text):
                offset = int(ref[2])
                if not 64 + boundary <= offset < info.data_pos:
                    raise ValueError("Invalid calibration offset in native comment")
            if update_x:
                # Omit the original X reference while shifting all other table pointers.
                text = field_pattern.sub(b"__PYCONLYSE_X_TABLE__", text, count=1)
            text = _TABLE_REFERENCE.sub(
                lambda ref: ref[1] + (b'%07d' % (int(ref[2]) + shift + len(x_table))) + ref[3], text
            )
            if update_x:
                text = text.replace(b"__PYCONLYSE_X_TABLE__", template % (64 + boundary + shift, len(axis)), 1)
            updated = text + metadata + x_table + tables
            if len(updated) > 65535 or (axis is not None and len(axis) > 9999):
                raise ValueError("Calibration exceeds the native header limits")
            struct.pack_into('<H', fixed, 2, len(updated))
            target.write(fixed)
            target.write(updated)
            digest = _copy_frames(source, target)
            target.flush()
            os.fsync(target.fileno())

        readback = HamamatsuFileOpener().read_critical_info(staged)
        if ((axis is not None and (readback.scaling_xunit != 'nm' or not np.array_equal(readback.wavelengths, axis)))
                or (axis is None and (readback.scaling_xunit != info.scaling_xunit
                                      or not np.array_equal(readback.wavelengths, info.wavelengths)))
                or readback.number_maps != count or readback.scaling_yunit != info.scaling_yunit
                or not np.array_equal(readback.timedelays, delays)
                or (update_y and time_origin_metadata(readback.header) != float(old_delays[0]))
                or (valid_columns is not None and spectral_calibration_metadata(readback.header) != (calibration_id, valid_columns))):
            raise ValueError("Staged native file calibration did not verify; original retained")
        with staged.open('rb') as stream:
            stream.seek(readback.data_pos)
            if _copy_frames(stream) != digest:
                raise ValueError("Staged native file frame bytes did not verify; original retained")
        if _signature(path.stat()) != _signature(original):
            raise ValueError("Native file changed during calibration; original retained")
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)
    return axis


# Existing sequence callers use the same byte writer as the single-image save.
embed_his_wavelengths = embed_native_axes
