'''
Created on 17 avr. 2015
"Read the Hamamatsu header,DATA, Time Delays and Wavelenghs for the given __filepath

@author: saldenisov
'''
import os
import struct

import numpy as np
from ERRORS import NoSuchFileType


# import logging
# module_logger = logging.getLogger(__name__)

def hamamatsuopener(filepath):
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

        # Size of datastructures in bytes
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
        return {'datastructures': _data,
                'timedelays': timedelays,
                'wavelengths': wavelengths}

#===============================================================================
# class HamamatsuFileOpener:
#     """
#     Opener for '.img' format used by STREAK-cameras,
#     developped by Hamamatsu Corporation.
# 
#     Takes *.img file opens it and extract datastructures,
#     timedelays, wavelengths as numpy arrays
#     """
# 
#     def __init__(self, filepath):
#         self.logger = logging.getLogger("MAIN." + __name__)
#         self.__filepath = filepath
#         self.__data = None
#         self.__timedelays = None
#         self.__wavelengths = None
# 
#     def read_data(self):
#         pos = 0
#         try:
#             fileextension = os.path.splitext(self.filepath)[1]
# 
#             if fileextension != '.img':
#                 raise NoSuchFileType
# 
#             with open(self.filepath, 'rb') as file:
#                 filedata = bytearray(file.read())
# 
#         except (FileNotFoundError, NoSuchFileType) as e:
#             self.logger.error(e)
#             raise
#         else:
#             # first 64 bites of settings
#             settings_header = filedata[pos:64]
#             pos += 64
# 
#             # header string
#             shift = int.from_bytes(settings_header[2:4], byteorder='little')
#             header = filedata[64:shift].decode(encoding='UTF-8')
#             pos += shift
# 
#             # Get file type
#             file_type = self.get_img_type(header)
# 
#             # Set scales parameters
#             scaling_xscale, scaling_xunit, scaling_yscale, scaling_yunit = self.set_scales_param(header)
# 
#             # Wavelength array size in pixels
#             wavelengths_length = int.from_bytes(settings_header[4:6],
#                                                 byteorder='little')
#             # Time array size in pixels
#             timedelays_length = int.from_bytes(settings_header[6:8],
#                                                byteorder='little')
#             # Data size type
#             if int.from_bytes(settings_header[12:14], byteorder='little') == 3:
#                 bytes_per_point = 4
#             if int.from_bytes(settings_header[12:14], byteorder='little') == 2:
#                 bytes_per_point = 2
#             if int.from_bytes(settings_header[12:14], byteorder='little') == 1:
#                 bytes_per_point = 1
# 
#             # Size of datastructures in bytes
#             size_data_bytes = bytes_per_point * timedelays_length * wavelengths_length
# 
#             # Data byte array
#             data_bytearray = filedata[pos: pos + size_data_bytes]
# 
#             # Data double array
#             try:
#                 data_array = np.frombuffer(data_bytearray, dtype='int32')
#                 self.__data = np.array(data_array.reshape(timedelays_length,
#                                                         wavelengths_length))
#             except (ValueError, RuntimeError) as e:
#                 self.logger.error('no DATA were read:' + str(e))
#                 raise
# 
#             # Arrays of wavelength and time-delays
#             try:
#                 self.__timedelays = self.get_timedelays_stat(filedata,
#                                                              timedelays_length,
#                                                              bytes_per_point,
#                                                              scaling_yunit,
#                                                              scaling_yscale,
#                                                              header,
#                                                              file_type)
#             except:
#                 self.logger.error('no timedelays were read')
#                 raise RuntimeError
# 
#             try:
#                 self.__wavelengths = self.get_wavelengths_stat(filedata,
#                                                                wavelengths_length,
#                                                                bytes_per_point,
#                                                                header,
#                                                                file_type)
#             except:
#                 self.logger.error('no wavelengths were read')
#                 raise RuntimeError
# 
#     def get_timedelays_stat(self, filedata,
#                             timedelays_length,
#                             bytes_per_point,
#                             scalingyunit,
#                             scalingyscale,
#                             header,
#                             file_type='Other'):
#         timedelays = np.empty(timedelays_length)
# 
#         if file_type == 'Normal':
#             from_ = int(header.split("ScalingYScalingFile=")
#                         [1][2:].split(",")[0])
#             timedelays_bytes = filedata[
#                 from_: from_ + timedelays_length * bytes_per_point]
#             timedelays = [(struct.unpack('f', timedelays_bytes[i: i + bytes_per_point])[0])
#                           for i in range(0, timedelays_length * bytes_per_point,
#                                          bytes_per_point)]
#         else:
#             divider = 1
#             if scalingyunit == 'ps':
#                 divider = 1000
#             timedelays = [i * scalingyscale /
#                           divider for i in range(timedelays_length)]
#         return np.array(timedelays)
# 
#     def get_wavelengths_stat(self, filedata,
#                              wavelength_length,
#                              bytes_per_point,
#                              header,
#                              file_type='Other'):
#         wavelengths = np.empty(wavelength_length)
#         if file_type == 'Normal':
#             from_ = int(header.split("ScalingXScalingFile=")
#                         [1][2:].split(",")[0])
#             wavelengts_bytes = filedata[
#                 from_: from_ + wavelength_length * bytes_per_point]
#             wavelengths = [struct.unpack('f', wavelengts_bytes[i: i + bytes_per_point])[0] for i in range(0, wavelength_length * bytes_per_point, bytes_per_point)]
#         else:
#             wavelengths = np.arange(wavelength_length)
# 
#         return np.array(wavelengths)
# 
#     def get_img_type(self, header):
#         type_ = 'Other'
#         xscaling_file = header.split("ScalingXScalingFile=")[1][1:6]
#         if xscaling_file != 'Other':
#             type_ = 'Normal'
#         return type_
# 
#     def set_scales_param(self, header):
#         scalingxscale = np.double(header.split("ScalingXScale=")[1].split(",")[0])
#         scalingxunit = header.split("ScalingXUnit=")[1][1:].split(",")[0][:-1]
# 
#         if scalingxunit == "No unit":
#             scalingxunit = 'pixel'
# 
#         scalingyscale = np.double(header.split("ScalingYScale=")[1].split(",")[0])
#         scalingyunit = header.split("ScalingYUnit=")[1][1:3]
# 
#         return scalingxscale, scalingxunit, scalingyscale, scalingyunit
# 
#     def get_essential_info(self):
#         return {'datastructures': self.datastructures, 'timedelays': self.timedelays, 'wavelengths': self.wavelengths}
# 
#     @property
#     def filepath(self):
#         return self.__filepath
# 
#     @property
#     def datastructures(self):
#         return self.__data
# 
#     @property
#     def timedelays(self):
#         return self.__timedelays
# 
#     @property
#     def wavelengths(self):
#         return self.__wavelengths
#===============================================================================

# =============================================================================
# import time
# start = time.time()
# Ham = hamamatsuopener('C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\test_error.img')
# print(Ham)
# end = time.time()
# =============================================================================