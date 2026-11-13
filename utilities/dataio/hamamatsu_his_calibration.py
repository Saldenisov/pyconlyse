"""Add a native HPD-TA wavelength table without changing any frame bytes."""
import hashlib
import os
from pathlib import Path
import re
import struct
from uuid import uuid4

import numpy as np

from utilities.dataio.hamamatsu_file_opener import HamamatsuFileOpener


_TABLE_REFERENCE = re.compile(rb'(=\"#)(\d{7})(,\d{4}\")')
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


def embed_his_wavelengths(path, wavelengths):
    """Publish a verified replacement only for the known camera-only HIS layout."""
    path = Path(path)
    if path.suffix.lower() != '.his' or path.is_symlink():
        raise ValueError("Expected a native HIS file")

    original = path.stat()
    info = HamamatsuFileOpener().read_critical_info(path)
    axis = np.asarray(wavelengths, dtype='<f4')
    if (axis.shape != (info.wavelengths_length,) or len(axis) < 2
            or not np.isfinite(axis).all()
            or not (np.all(np.diff(axis) > 0) or np.all(np.diff(axis) < 0))):
        raise ValueError("Invalid wavelength table for HIS detector width")
    if info.scaling_xunit == 'nm':
        if not np.array_equal(info.wavelengths, axis):
            raise ValueError("HIS already has a different wavelength calibration")
        return axis
    if info.file_type != 'Other':
        raise ValueError("Unsupported HIS spectral header; original retained")

    # A sibling inherits the experiment folder's permissions on Windows.
    staged = path.with_name(f'.his-calibration-{uuid4().hex}.his')
    try:
        with path.open('rb') as source, staged.open('xb') as target:
            fixed = bytearray(source.read(64))
            comment = source.read(info.data_pos - 64)
            count = struct.unpack_from('<H', fixed, 14)[0] or 1
            kind = struct.unpack_from('<H', fixed, 12)[0]
            frame_size = info.wavelengths_length * info.timedelays_length * info.bytes_per_point
            if (fixed[:2] != b'IM' or kind not in (1, 2, 3)
                    or count * (64 + frame_size) + len(comment) != original.st_size):
                raise ValueError("Unsupported or incomplete native HIS sequence")
            # The first comment holds all calibration tables. Identify the
            # binary boundary by native absolute offsets before changing text.
            refs = list(_TABLE_REFERENCE.finditer(comment))
            starts = [int(ref[2]) for ref in refs if ref.start() + 64 < int(ref[2]) < info.data_pos]
            boundary = min(starts, default=info.data_pos) - 64
            text, tables = comment[:boundary], comment[boundary:]
            matches = list(_PIXEL_X.finditer(text))
            if len(matches) != 1:
                raise ValueError("Expected one uncalibrated X field; original HIS retained")
            x_field = matches[0]
            template = b'ScalingXType=2,ScalingXScale=1,ScalingXUnit="nm",ScalingXScalingFile="#%07d,%04d"'
            placeholder = template % (0, len(axis))
            shift = len(placeholder) - len(x_field[0])
            x_offset = 64 + boundary + shift
            for ref in _TABLE_REFERENCE.finditer(text):
                offset = int(ref[2])
                if not 64 + boundary <= offset < info.data_pos:
                    raise ValueError("Invalid calibration offset in native HIS comment")
            text = _TABLE_REFERENCE.sub(
                lambda ref: ref[1] + (b'%07d' % (int(ref[2]) + shift + axis.nbytes)) + ref[3], text
            )
            text = _PIXEL_X.sub(template % (x_offset, len(axis)), text, count=1)
            updated = text + axis.tobytes() + tables
            if len(updated) > 65535 or len(axis) > 9999:
                raise ValueError("Calibration exceeds the native HIS header limits")
            struct.pack_into('<H', fixed, 2, len(updated))
            target.write(fixed)
            target.write(updated)
            digest = _copy_frames(source, target)
            target.flush()
            os.fsync(target.fileno())

        readback = HamamatsuFileOpener().read_critical_info(staged)
        if (readback.scaling_xunit != 'nm' or not np.array_equal(readback.wavelengths, axis)
                or readback.number_maps != count or readback.scaling_yunit != info.scaling_yunit
                or not np.array_equal(readback.timedelays, info.timedelays)):
            raise ValueError("Staged HIS calibration did not verify; original retained")
        with staged.open('rb') as stream:
            stream.seek(readback.data_pos)
            if _copy_frames(stream) != digest:
                raise ValueError("Staged HIS frame bytes did not verify; original retained")
        if _signature(path.stat()) != _signature(original):
            raise ValueError("Native HIS changed during calibration; original retained")
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)
    return axis
