"""Implementation for measure_callback and related operations."""

from __future__ import annotations


def _bind_avaspec_msl_original_backup_methods_measure_callback(api):
    """Bind implementation to the owning module and its runtime state."""

    def measure_callback(self, num_measurements, callback=None):
        """Starts measurement on the spectrometer.

        Parameters
        ----------
        num_measurements : :class:`int`
            Number of measurements to acquire. Use -1 to measure continuously until
            :meth:`.stop_measure` is called.
        callback : :attr:`MeasureCallback`, optional
            A function to notify application measurement result data is available.
            The DLL will call the given function to notify a measurement is ready and pass
            two parameters. The first parameter is a reference to the DLL handle. The
            second parameter is a reference to an integer value: `SUCCESS` (``0``) if a new
            scan is available, or the number of scans that were saved in RAM (if `m_StoreToRAM`
            parameter > 0, see :class:`ControlSettingsType`), or `INVALID_MEAS_DATA` (``-8``).
            Set this value to :data:`None` if a callback is not needed.

        Examples
        --------
        .. code-block:: python

            from msl.equipment.resources.avantes import MeasureCallback

            @MeasureCallback
            def avantes_callback(handle, info):
                print('The DLL handle is:', handle.contents.value)
                if info.contents.value == 0:  # equals 0 if everything is okay
                    print('  callback data:', ava.get_data())

            # here "ava" is a reference to the AvaSpec class
            ava.measure_callback(-1, avantes_callback)

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_MeasureCallback(self._handle, callback, num_measurements)

    def poll_scan(self):
        """Determines if new measurement results are available.

        Returns
        -------
        :class:`int`
            Whether there is a scan available: 0 (No) or 1 (Yes).

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        return self.sdk.AVS_PollScan(self._handle)

    def prepare_measure(self, config):
        """Prepares measurement on the spectrometer using the specified measurement configuration.

        Parameters
        ----------
        config : :class:`.MeasConfigType`
            The measurement configuration.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        if not isinstance(config, api.MeasConfigType):
            self.raise_exception('Must pass in a MeasConfigType object')
        self.sdk.AVS_PrepareMeasure(self._handle, config)

    def register(self, handle):
        """Installs an application windows handle to which device
        attachment/removal messages have to be sent.

        Parameters
        ----------
        handle : :class:`ctypes.c_void_p`
            Application window handle.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_Register(handle)

    def reset_device(self):
        """Performs a hard reset on the given spectrometer.

        This function only works with the AS7010 platform.

        During reset of the spectrometer, all spectrometer HW modules (microprocessor
        and USB controller) will be reset at once. The spectrometer will start its reset
        procedure right after sending the command response back to the host.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_ResetDevice(self._handle)

    def set_analog_out(self, port_id, value):
        """Sets the analog output value for the specified analog identifier.

        Parameters
        ----------
        port_id : :class:`int`
            Identifier for one of the two output signals:

            * AS5216:

                * 0 = AO1 = pin 17 at 26-pins connector
                * 1 = AO2 = pin 26 at 26-pins connector

            * Mini:

                * 0 = AO1 = Pin 12 on Micro HDMI = Pin 10 on HDMI terminal
                * 1 = AO2 = Pin 14 on Micro HDMI = Pin 12 on HDMI terminal

            * AS7010:

                * 0 = AO1 = pin 17 at 26-pins connector
                * 1 = AO2 = pin 26 at 26-pins connector

        value : :class:`float`
            DAC value to be set in Volts (internally an 8-bits DAC is used) with range 0 - 5.0V.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_SetAnalogOut(self._handle, port_id, value)

    def set_digital_out(self, port_id, value):
        """Sets the digital output value for the specified digital identifier.

        Parameters
        ----------
        port_id : :class:`int`
            Identifier for one of the 10 output signals:

            * AS5216:

                * 0 = DO1 = pin 11 at 26-pins connector
                * 1 = DO2 = pin 2 at 26-pins connector
                * 2 = DO3 = pin 20 at 26-pins connector
                * 3 = DO4 = pin 12 at 26-pins connector
                * 4 = DO5 = pin 3 at 26-pins connector
                * 5 = DO6 = pin 21 at 26-pins connector
                * 6 = DO7 = pin 13 at 26-pins connector
                * 7 = DO8 = pin 4 at 26-pins connector
                * 8 = DO9 = pin 22 at 26-pins connector
                * 9 = DO10 = pin 25 at 26-pins connector

            * Mini:

                * 0 = DO1 = Pin 7 on Micro HDMI = Pin 5 on HDMI terminal
                * 1 = DO2 = Pin 5 on Micro HDMI = Pin 3 on HDMI Terminal
                * 2 = DO3 = Pin 3 on Micro HDMI = Pin 1 on HDMI Terminal
                * 3 = DO4 = Pin 1 on Micro HDMI = Pin 19 on HDMI Terminal
                * 4 = DO5 = Pin 4 on Micro HDMI = Pin 2 on HDMI Terminal
                * 5 = DO6 = Pin 2 on Micro HDMI = Pin 14 on HDMI Terminal
                * 6 = Not used
                * 7 = Not used
                * 8 = Not used
                * 9 = Not used

            * AS7010:

                * 0 = DO1 =pin 11 at 26-pins connector
                * 1 = DO2 = pin 2 at 26-pins connector
                * 2 = DO3 = pin 20 at 26-pins connector
                * 3 = DO4 = pin 12 at 26-pins connector
                * 4 = DO5 = pin 3 at 26-pins connector
                * 5 = DO6 = pin 21 at 26-pins connector
                * 6 = DO7 = pin 13 at 26-pins connector
                * 7 = DO8 = pin 4 at 26-pins connector
                * 8 = DO9 = pin 22 at 26-pins connector
                * 9 = DO10 = pin 25 at 26-pins connector

        value : :class:`int`
            The value to be set (0 or 1).

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_SetDigOut(self._handle, port_id, value)

    def set_oem_parameter(self, parameter):
        """Sends the OEM data structure to the spectrometer.

        Parameters
        ----------
        parameter : :class:`.OemDataType`
            The OEM data structure.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        if not isinstance(parameter, api.OemDataType):
            self.raise_exception('Must pass in an OemDataType object')
        self.sdk.AVS_SetOemParameter(self._handle, parameter)

    def set_parameter(self, parameter):
        """Overwrites the device configuration.

        Please note that :class:`OemDataType` is part of the DeviceConfigType in EEPROM (see
        section 3.5 of DLL manual). Precautions must be taken to prevent OEM data overwrites
        when using :meth:`.set_parameter` method together with :meth:`.set_oem_parameter`.

        Parameters
        ----------
        parameter : :class:`.DeviceConfigType`
            The device parameters.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        if not isinstance(parameter, api.DeviceConfigType):
            self.raise_exception('Must pass in a DeviceConfigType object')
        self.sdk.AVS_SetParameter(self._handle, parameter)

    def set_prescan_mode(self, boolean):
        """If a prescan is set, the first measurement result will be skipped.

        This function is only useful for the AvaSpec-3648 because this detector
        can be operated in prescan mode, or clear-buffer mode (see DLL manual).

        Parameters
        ----------
        boolean : :class:`bool`
            If :data:`True`, the first measurement result will be skipped (prescan mode),
            else the detector will be cleared before each new scan (clear-buffer mode).

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_SetPrescanMode(self._handle, boolean)

    def set_pwm_out(self, port_id, frequency, duty_cycle):
        """Selects the PWM functionality for the specified digital output.

        The PWM functionality is not supported on the Mini.

        Parameters
        ----------
        port_id : :class:`int`
            Identifier for one of the 6 PWM output signals:

            * 0 = DO1 = pin 11 at 26-pins connector
            * 1 = DO2 = pin 2 at 26-pins connector
            * 2 = DO3 = pin 20 at 26-pins connector
            * 4 = DO5 = pin 3 at 26-pins connector
            * 5 = DO6 = pin 21 at 26-pins connector
            * 6 = DO7 = pin 13 at 26-pins connector

        frequency : :class:`int`
            Desired PWM frequency (500 - 300000) [Hz]. For the AS5216, the frequency of
            outputs 0, 1 and 2 is the same (the last specified frequency is used) and
            also the frequency of outputs 4, 5 and 6 is the same. For the AS7010, you
            can define six different frequencies.
        duty_cycle : :class:`int`
            Percentage high time in one cycle (0 - 100). For the AS5216, channels 0,
            1 and 2 have a synchronized rising edge, the same holds for channels 4, 5
            and 6. For the AS7010, rising edges are unsynchronized.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_SetPwmOut(self._handle, port_id, frequency, duty_cycle)

    def set_sensitivity_mode(self, value):
        """Set the sensitivity mode.

        This method is supported by the following detector types: HAMS9201,
        HAMG9208_512, SU256LSB and SU512LDB with the appropriate firmware version.

        Parameters
        ----------
        value : :class:`int`
            0 for low noise, >0 for high sensitivity

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_SetSensitivityMode(self._handle, value)

    def set_sync_mode(self, enable):
        """Disables/enables support for synchronous measurement.

        Parameters
        ----------
        enable : :class:`bool`
            :data:`False` to disable sync mode, :data:`True` to enable sync mode.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_SetSyncMode(self._handle, int(bool(enable)))

    def stop_measure(self):
        """Stops the measurement.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_StopMeasure(self._handle)

    def suppress_stray_light(self, factor):
        """Returns the stray light corrected pixel values of a dark corrected measurement.

        Parameters
        ----------
        factor : :class:`float`
            Multiplication factor for the stray light algorithm.

        Returns
        -------
        :class:`numpy.ndarray`
            Scope minus dark.
        :class:`numpy.ndarray`
            Stray light suppressed.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        x = -9e99
        src = api.np.ones(api.MAX_NR_PIXELS, dtype=api.np.double) * x
        dest = api.np.ones(api.MAX_NR_PIXELS, dtype=api.np.double) * x
        self.sdk.AVS_SuppressStrayLight(
            self._handle,
            factor,
            src.ctypes.data_as(api.POINTER(api.c_double)),
            dest.ctypes.data_as(api.POINTER(api.c_double))
        )
        return src[src > x], dest[dest > x]

    def update_eth_devices(self, nmax=16):
        """Return the number of Ethernet devices that are connected to the computer.

        Internally checks the list of connected Ethernet devices and returns the number of devices
        attached. If the :attr:`~msl.equipment.record_types.ConnectionRecord.properties`
        attribute contains a key ``'port_id'`` with a value of ``-1`` then the returned value
        also includes the number of USB devices.

        Parameters
        ----------
        nmax : :class:`int`, optional
            The maximum number of devices that can be found.

        Returns
        -------
        :class:`list` of :class:`.BroadcastAnswerType`
            The information about the devices.
        """
        size = nmax * api.sizeof(api.BroadcastAnswerType)
        required_size = api.c_uint32()
        types = (api.BroadcastAnswerType * nmax)()
        n = self.sdk.AVS_UpdateETHDevices(size, required_size, types)
        return [types[i] for i in range(n)]

    def update_usb_devices(self):
        """Return the number of USB devices that are connected to the computer.

        Internally checks the list of connected USB devices and returns the number of devices
        attached. If the :attr:`~msl.equipment.record_types.ConnectionRecord.properties`
        attribute contains a key ``'port_id'`` with a value of ``-1`` then the returned value
        also includes the number of Ethernet devices.

        Returns
        -------
        :class:`int`
            The number of devices found.
        """
        return self.sdk.AVS_UpdateUSBDevices()

    def use_high_res_adc(self, enable):
        """Enable the 16-bit AD converter.

        When using the 16 bit ADC in full High Resolution mode (0..65535), please note that the
        irradiance intensity calibration, as well as the nonlinearity calibration are based on the 14bit
        ADC range. Therefore, if using the nonlinearity correction or irradiance calibration in your
        own software using the High Resolution mode, you need to apply the additional correction
        with ADCFactor (= 4.0), as explained in detail in section 4.6.1 and 4.6.3 of the manual.

        Parameters
        ----------
        enable : :class:`bool`
            If :data:`True` use a 16-bit AD converter, otherwise use a 14-bit ADC.

        Raises
        ------
        ~msl.equipment.exceptions.AvantesError
            If there was an error.
        """
        self.sdk.AVS_UseHighResAdc(self._handle, bool(enable))
    return {
        "measure_callback": measure_callback,
        "poll_scan": poll_scan,
        "prepare_measure": prepare_measure,
        "register": register,
        "reset_device": reset_device,
        "set_analog_out": set_analog_out,
        "set_digital_out": set_digital_out,
        "set_oem_parameter": set_oem_parameter,
        "set_parameter": set_parameter,
        "set_prescan_mode": set_prescan_mode,
        "set_pwm_out": set_pwm_out,
        "set_sensitivity_mode": set_sensitivity_mode,
        "set_sync_mode": set_sync_mode,
        "stop_measure": stop_measure,
        "suppress_stray_light": suppress_stray_light,
        "update_eth_devices": update_eth_devices,
        "update_usb_devices": update_usb_devices,
        "use_high_res_adc": use_high_res_adc,
    }
