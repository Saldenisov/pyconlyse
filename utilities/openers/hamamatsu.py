'''
Created on 17 avr. 2015
"Read the Hamamatsu header,DATA, Time Delays and Wavelenghs for the given __filepath

@author: saldenisov
'''
from errors.myexceptions import NoSuchFileType
import struct
import numpy as np
import os
from pathlib import Path

# import logging
# module_logger = logging.getLogger(__name__)

def HamamatsuImgOpener(filepath: Path) -> :
    def get_timedelays_stat(filedata,
                            timedelays_length,
                            bytes_per_point,
                            scalingyunit,
                            scalingyscale,
                            header,
                            file_type='Other'):
        timedelays = np.empty(timedelays_length)

        if file_type == 'Normal':
            from_ = int(header.split("ScalingYScalingFile=")
                        [1][2:].split(",")[0])
            timedelays_bytes = filedata[
                from_: from_ + timedelays_length * bytes_per_point]
            try:
                timedelays = [(struct.unpack('f', timedelays_bytes[i: i + bytes_per_point])[0])
                          for i in range(0, timedelays_length * bytes_per_point,
                                         bytes_per_point)]
            except struct.error:
                raise
        else:
            divider = 1
            if scalingyunit == 'ps':
                divider = 1000
            timedelays = [i * scalingyscale /
                          divider for i in range(timedelays_length)]
        return np.array(timedelays)

    def get_wavelengths_stat(filedata,
                             wavelength_length,
                             bytes_per_point,
                             header,
                             file_type='Other'):
        wavelengths = np.empty(wavelength_length)
        if file_type == 'Normal':
            from_ = int(header.split("ScalingXScalingFile=")
                        [1][2:].split(",")[0])
            wavelengts_bytes = filedata[
                from_: from_ + wavelength_length * bytes_per_point]
            try:
                wavelengths = [struct.unpack('f', wavelengts_bytes[i: i + bytes_per_point])[0] for i in range(0, wavelength_length * bytes_per_point, bytes_per_point)]
            except struct.error:
                raise
        else:
            wavelengths = np.arange(wavelength_length)

        return np.array(wavelengths)

    def get_img_type(header):
        type_ = 'Other'
        xscaling_file = header.split("ScalingXScalingFile=")[1][1:6]
        if xscaling_file != 'Other':
            type_ = 'Normal'
        return type_

    def set_scales_param(header):
        scalingxscale = np.double(header.split("ScalingXScale=")[1].split(",")[0])
        scalingxunit = header.split("ScalingXUnit=")[1][1:].split(",")[0][:-1]

        if scalingxunit == "No unit":
            scalingxunit = 'pixel'

        scalingyscale = np.double(header.split("ScalingYScale=")[1].split(",")[0])
        scalingyunit = header.split("ScalingYUnit=")[1][1:3]

        return scalingxscale, scalingxunit, scalingyscale, scalingyunit

    pos = 0
    try:
        fileextension = os.path.splitext(filepath)[1]

        if fileextension != '.img':
            raise NoSuchFileType

        with open(filepath, 'rb') as file:
            filedata = bytearray(file.read())

    except (FileNotFoundError, NoSuchFileType, ValueError) as e:
        raise
    else:
        # first 64 bites of settings
        settings_header = filedata[pos:64]
        pos += 64

        # header string
        shift = int.from_bytes(settings_header[2:4], byteorder='little')
        header = filedata[64:shift].decode(encoding='UTF-8')
        pos += shift

        # Get file type
        file_type = get_img_type(header)

        # Set scales parameters
        scaling_xscale, scaling_xunit, scaling_yscale, scaling_yunit = set_scales_param(header)

        # Wavelength array size in pixels
        wavelengths_length = int.from_bytes(settings_header[4:6],
                                            byteorder='little')
        # Time array size in pixels
        timedelays_length = int.from_bytes(settings_header[6:8],
                                            byteorder='little')
        # Data size type
        if int.from_bytes(settings_header[12:14], byteorder='little') == 3:
            bytes_per_point = 4
        if int.from_bytes(settings_header[12:14], byteorder='little') == 2:
            bytes_per_point = 2
        if int.from_bytes(settings_header[12:14], byteorder='little') == 1:
            bytes_per_point = 1

        # Size of data in bytes
        size_data_bytes = bytes_per_point * timedelays_length * wavelengths_length

        # Data byte array
        data_bytearray = filedata[pos: pos + size_data_bytes]

        # Data double array
        try:
            data_array = np.frombuffer(data_bytearray, dtype='int32')
            _data = np.array(data_array.reshape(timedelays_length,
                                                wavelengths_length))
        except (ValueError, RuntimeError):
            raise

        # Arrays of wavelength and time-delays
        try:
            timedelays = get_timedelays_stat(filedata,
                                             timedelays_length,
                                             bytes_per_point,
                                             scaling_yunit,
                                             scaling_yscale,
                                             header,
                                             file_type)
        except struct.error:
            raise RuntimeError('no timedelays were read')

        try:
            wavelengths = get_wavelengths_stat(filedata,
                                               wavelengths_length,
                                               bytes_per_point,
                                               header,
                                               file_type)
        except struct.error:
            raise RuntimeError('no wavelengths were read')
        return {'data': _data,
                'timedelays': timedelays,
                'wavelengths': wavelengths}
