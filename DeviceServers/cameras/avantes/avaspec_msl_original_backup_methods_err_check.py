"""Implementation for _err_check and related operations."""

from __future__ import annotations


def _bind_avaspec_msl_original_backup_methods_err_check(api):
    """Bind implementation to the owning module and its runtime state."""

    def _err_check(self, result, func, arguments):
        self.log_errcheck(result, func, arguments)
        if result < 0:
            error_name, msg = api.ERROR_CODES.get(result, ('UNKNOWN_ERROR', 'Unknown error'))
            self.raise_exception('{}: {}'.format(error_name, msg))
        return result

    def _check_bool(self, result, func, arguments):
        self.log_errcheck(result, func, arguments)
        if not result:
            self.raise_exception('The {} function returned False'.format(func))

    def activate(self):
        """Activates the spectrometer for communication.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        out = api.Avantes.find(path=self.path)
        if not out:
            self.raise_exception('Cannot activate. No devices found.')
        for item in out:
            if item.SerialNumber.decode() == self.equipment_record.serial:
                self._handle = self.sdk.AVS_Activate(item)
                if self._handle == api.INVALID_AVS_HANDLE_VALUE:
                    self.raise_exception('Invalid handle')
                api._handles.append(self._handle)
                return
        self.raise_exception('Did not find the Avantes serial number {!r}'
                             'in the list of devices.'.format(self.equipment_record.serial))

    def deactivate(self):
        """Closes communication with the spectrometer."""
        if self._handle is not None and self._handle != api.INVALID_AVS_HANDLE_VALUE:
            self.sdk.AVS_Deactivate(self._handle)
            api._handles.remove(self._handle)
            self._handle = None

    def get_analog_in(self, analog_id):
        """Get the status of the specified analog input.

        Parameters
        ----------
        analog_id : :class:`int`
            The identifier of the analog input to get.

            * AS5216:

                * 0 = thermistor on optical bench (NIR 2.0 / NIR2.2 / NIR 2.5 / TEC)
                * 1 = 1V2
                * 2 = 5VIO
                * 3 = 5VUSB
                * 4 = AI2 = pin 18 at 26-pins connector
                * 5 = AI1 = pin 9 at 26-pins connector
                * 6 = NTC1 onboard thermistor
                * 7 = Not used

            * Mini:

                * 0 = NTC1 onboard thermistor
                * 1 = Not used
                * 2 = Not used
                * 3 = Not used
                * 4 = AI2 = pin 13 on micro HDMI = pin 11 on HDMI Terminal
                * 5 = AI1 = pin 16 on micro HDMI = pin 17 on HDMI Terminal
                * 6 = Not used
                * 7 = Not used

            * AS7010:

                * 0 = thermistor on optical bench (NIR 2.0 / NIR2.2 / NIR 2.5 / TEC)
                * 1 = Not used
                * 2 = Not used
                * 3 = Not used
                * 4 = AI2 = pin 18 at 26-pins connector
                * 5 = AI1 = pin 9 at 26-pins connector
                * 6 = digital temperature sensor, returns degrees Celsius, not Volts
                * 7 = Not used

        Returns
        -------
        :class:`float`
            The analog input value [Volts or degrees Celsius].

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        ain = api.c_float()
        self.sdk.AVS_GetAnalogIn(self._handle, analog_id, ain)
        return ain.value

    def get_com_port_name(self):
        """Get the IP address of the device.

        Returns
        -------
        :class:`str`
            The IP address of the device.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        device_id = api.AvsIdentityType()
        device_id.SerialNumber = self.equipment_record.serial.encode()
        name = api.create_string_buffer(255)
        self.sdk.AVS_GetComPortName(device_id, name, len(name))
        return name.value.decode()

    def get_com_type(self):
        """Get the communication protocol.

        Returns
        -------
        :class:`str`
            The communication type as defined below:

            * RS232 = 0
            * USB5216 = 1
            * USBMINI = 2
            * USB7010 = 3
            * ETH7010 = 4
            * UNKNOWN = -1

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        device_id = api.AvsIdentityType()
        device_id.SerialNumber = self.equipment_record.serial.encode()
        typ = api.c_int32(-1)
        self.sdk.AVS_GetComType(device_id, typ)
        return typ.value

    def get_dark_pixel_data(self):
        """Get the optically black pixel values of the last performed measurement.

        You must call :meth:`get_data` before you call this method.

        Returns
        -------
        :class:`numpy.ndarray`
            The dark pixels.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        # from the docs the maximum size is size=18 for the AvaSpec-2048-USB2 and AvaSpec-2048L-USB2
        values = api.np.zeros(32, dtype=api.np.double)  # make it bigger than 18
        self.sdk.AVS_GetDarkPixelData(self._handle, values.ctypes.data_as(api.POINTER(api.c_double)))
        return values[values > 0]

    def get_dll_version(self):
        """Get the DLL version number.

        Returns
        -------
        :class:`str`
            The DLL version number
        """
        version = api.create_string_buffer(255)
        self.sdk.AVS_GetDLLVersion(version)
        return version.value.decode()

    def get_digital_in(self, digital_id):
        """Get the status of the specified digital input.

        Parameters
        ----------
        digital_id : :class:`int`
            The identifier of the digital input to get.

            * AS5216:

                * 0 = DI1 = Pin 24 at 26-pins connector
                * 1 = DI2 = Pin 7 at 26-pins connector
                * 2 = DI3 = Pin 16 at 26-pins connector

            * Mini:

                * 0 = DI1 = Pin 7 on Micro HDMI = Pin 5 on HDMI terminal
                * 1 = DI2 = Pin 5 on Micro HDMI = Pin 3 on HDMI Terminal
                * 2 = DI3 = Pin 3 on Micro HDMI = Pin 1 on HDMI Terminal
                * 3 = DI4 = Pin 1 on Micro HDMI = Pin 19 on HDMI Terminal
                * 4 = DI5 = Pin 4 on Micro HDMI = Pin 2 on HDMI Terminal
                * 5 = DI6 = Pin 2 on Micro HDMI = Pin 14 on HDMI Terminal

            * AS7010:

                * 0 = DI1 = Pin 24 at 26-pins connector
                * 1 = DI2 = Pin 7 at 26-pins connector
                * 2 = DI3 = Pin 16 at 26-pins

        Returns
        -------
        :class:`int`
            The digital input value.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        din = api.c_ubyte()
        self.sdk.AVS_GetDigIn(self._handle, digital_id, din)
        return din.value

    def get_handle_from_serial(self, serial=None):
        """Get the handle ID for the specified serial number.

        Parameters
        ----------
        serial : :class:`str`
            The serial number. Default is to get the status for this object.

        Returns
        -------
        :class:`int`
            The handle.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        if serial is None:
            serial = self.equipment_record.serial.encode()
        elif not isinstance(serial, bytes):
            serial = serial.encode()
        return self.sdk.AVS_GetHandleFromSerial(serial)

    def find(path='avaspecx64.dll', port_id=-1, nmax=16):
        """Returns device information for each spectrometer that is connected.

        Parameters
        ----------
        path : :class:`str`
            The path to the Avantes SDK.
        port_id : :class:`int`
            ID of port to be used. One of:

                * -1: Use both Ethernet (AS7010) and USB ports
                * 0: Use USB port
                * 1..255: Not supported in v9.7 of the SDK
                * 256: Use Ethernet port (AS7010)

        nmax : :class:`int`, optional
            The maximum number of devices that can be in the list.

        Returns
        -------
        :class:`list` of :class:`.AvsIdentityType`
            The information about the devices.
        """
        libtype = 'windll' if api.IS_WINDOWS else 'cdll'
        lib = api.LoadLibrary(path, libtype=libtype).lib

        ret = lib.AVS_Init(port_id)
        if ret == 0:
            return []

        size = nmax * api.sizeof(api.AvsIdentityType)
        required_size = api.c_uint32()
        types = (api.AvsIdentityType * nmax)()

        lib.AVS_GetList.argtypes = [api.c_uint32, api.POINTER(api.c_uint32), api.POINTER(api.AvsIdentityType)]
        n = lib.AVS_GetList(size, required_size, types)
        if n < 0:
            error_name, msg = api.ERROR_CODES.get(n, ('UNKNOWN_ERROR', 'Unknown error'))
            raise api.AvantesError('{}: {}'.format(error_name, msg))

        return [types[i] for i in range(n)]

    def get_status_by_serial(self, serial=None):
        """Get the handle ID for the specified serial number.

        Parameters
        ----------
        serial : :class:`str`, optional
            The serial number. Default is to get the status for this object.

        Returns
        -------
        :class:`int`
            The status.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        if serial is None:
            serial = self.equipment_record.serial.encode()
        elif not isinstance(serial, bytes):
            serial = serial.encode()
        status = api.c_int32()
        self.sdk.AVS_GetStatusBySerial(serial, status)
        return status.value

    def done(self):
        """Closes communication and releases internal storage."""
        if self._sdk is not None:
            self.sdk.AVS_Done()

    def disconnect(self):
        """Closes communication with the spectrometer."""
        self.deactivate()
        if not api._handles:
            self.done()

    def get_ip_config(self):
        """Retrieve IP settings from the spectrometer.

        Use this function to read the Ethernet settings of the spectrometer, without
        having to read the complete device configuration structure.

        Returns
        -------
        :class:`.EthernetSettingsType`
            The Ethernet settings of the spectrometer.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        eth = api.EthernetSettingsType()
        self.sdk.AVS_GetIpConfig(self._handle, eth)
        return eth

    def get_lambda(self):
        """Returns the wavelength values corresponding to the pixels if available.

        Returns
        -------
        :class:`numpy.ndarray`
            The wavelength value of each pixel.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        values = api.np.zeros(api.MAX_NR_PIXELS, dtype=api.np.double)
        self.sdk.AVS_GetLambda(self._handle, values.ctypes.data_as(api.POINTER(api.c_double)))
        return values[values > 0]

    def get_num_devices(self):
        """Scans for attached devices and returns the number of devices detected.

        Deprecated function, replaced by :meth:`.update_usb_devices`. The
        functionality is identical.

        Returns
        -------
        :class:`int`
            The number of devices found.
        """
        return self.sdk.AVS_GetNrOfDevices()

    def get_oem_parameter(self):
        """Returns the OEM data structure available on the spectrometer.

        Returns
        -------
        :class:`.OemDataType`
            The OEM parameters.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        odt = api.OemDataType()
        self.sdk.AVS_GetOemParameter(self._handle, odt)
        return odt

    def get_parameter(self):
        """Returns the device information of the spectrometer.

        Returns
        -------
        :class:`.DeviceConfigType`
            The device parameters.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        dct = api.DeviceConfigType()
        required_size = api.c_uint32()
        self.sdk.AVS_GetParameter(self._handle, api.sizeof(dct), required_size, dct)
        return dct

    def get_saturated_pixels(self):
        """Returns, for each pixel, if a pixel was saturated (1) or not (0).

        Returns
        -------
        :class:`numpy.ndarray`
            The saturation state of each pixel.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        values = api.np.ones(api.MAX_NR_PIXELS, dtype=api.np.uint8) * 9
        self.sdk.AVS_GetSaturatedPixels(self._handle, values.ctypes.data_as(api.POINTER(api.c_ubyte)))
        return values[values < 9]

    def get_version_info(self):
        """Returns software version information.

        Returns
        -------
        :class:`str`
            FPGA software version.
        :class:`str`
            Firmware version.
        :class:`str`
            DLL version.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        fpga = api.create_string_buffer(16)
        fm = api.create_string_buffer(16)
        dll = api.create_string_buffer(16)
        self.sdk.AVS_GetVersionInfo(self._handle, fpga, fm, dll)
        return tuple(obj.value.decode() for obj in [fpga, fm, dll])

    def get_data(self):
        """Returns the pixel values of the last performed measurement.

        Returns
        -------
        :class:`int`
            Tick count the last pixel of the spectrum was received by the microcontroller.
            Ticks are in 10 microsecond units since the spectrometer started.
        :class:`numpy.ndarray`
            The pixel values.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        ticks = api.c_uint32()
        values = api.np.ones(api.MAX_NR_PIXELS, dtype=api.np.double) * -1.0
        self.sdk.AVS_GetScopeData(self._handle, ticks, values.ctypes.data_as(api.POINTER(api.c_double)))
        return ticks.value, values[values > -1.0]

    def get_num_pixels(self):
        """Returns the number of pixels of a spectrometer.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        n = api.c_uint16()
        self.sdk.AVS_GetNumPixels(self._handle, n)
        return n.value

    def heartbeat(self, req_type):
        """Monitor the (heartbeat) functions of the spectrometer.

        This function applies only to the AS7010 platform. See the DLL manual for more details.

        Parameters
        ----------
        req_type : :class:`int`
            The heartbeat request values used to control heartbeat functions.

        Returns
        -------
        :class:`.HeartbeatRespType`
            The heartbeat response structure received from the spectrometer.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        resp = api.HeartbeatRespType()
        self.sdk.AVS_Heartbeat(self._handle, req_type, resp)
        return resp

    def init(self, port_id):
        """Initializes the communication interface with the spectrometers and the internal data structures.

        For Ethernet devices this function will create a list of available Ethernet spectrometers
        within all the network interfaces of the host.

        Parameters
        ----------
        port_id : :class:`int`
            ID of port to be used. One of:

                * -1: Use both Ethernet (AS7010) and USB ports
                * 0: Use USB port
                * 1..255: Not supported in v9.7 of the SDK
                * 256: Use Ethernet port (AS7010)

        Returns
        -------
        :class:`int`
            On success, the number of connected or found devices.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If no devices were found.
        """
        ret = self.sdk.AVS_Init(port_id)
        if ret == 0:
            self.raise_exception('No Avantes devices were found')
        return ret

    def measure(self, num_measurements, window_handle=None):
        """Starts measurement on the spectrometer.

        Parameters
        ----------
        num_measurements : :class:`int`
            Number of measurements to acquire. Use -1 to measure continuously until
            :meth:`.stop_measure` is called.
        window_handle : :class:`ctypes.c_void_p`, optional
            Window handle to notify application measurement result data is available.
            The DLL sends a message to the window with command: `WM_MEAS_READY`, with
            `SUCCESS` (``0``), the number of scans that were saved in RAM (if `m_StoreToRAM`
            parameter > 0, see :class:`ControlSettingsType`), or `INVALID_MEAS_DATA`
            as `WPARM` value and `a_hDevice` as `LPARM` value. Set this value to :data:`None`
            if a callback is not needed.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_Measure(self._handle, window_handle, num_measurements)

    return {
        "_err_check": _err_check,
        "_check_bool": _check_bool,
        "activate": activate,
        "deactivate": deactivate,
        "get_analog_in": get_analog_in,
        "get_com_port_name": get_com_port_name,
        "get_com_type": get_com_type,
        "get_dark_pixel_data": get_dark_pixel_data,
        "get_dll_version": get_dll_version,
        "get_digital_in": get_digital_in,
        "get_handle_from_serial": get_handle_from_serial,
        "find": find,
        "get_status_by_serial": get_status_by_serial,
        "done": done,
        "disconnect": disconnect,
        "get_ip_config": get_ip_config,
        "get_lambda": get_lambda,
        "get_num_devices": get_num_devices,
        "get_oem_parameter": get_oem_parameter,
        "get_parameter": get_parameter,
        "get_saturated_pixels": get_saturated_pixels,
        "get_version_info": get_version_info,
        "get_data": get_data,
        "get_num_pixels": get_num_pixels,
        "heartbeat": heartbeat,
        "init": init,
        "measure": measure,
    }
