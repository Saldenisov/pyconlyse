"""Legacy full-profile RemoteEx instrument readback."""


def refresh_external_instruments(self):
    self.snapshot.current_wavelength = self._safe_query(
        self.get_device_parameter, "Spec", "Wavelength"
    )
    self.snapshot.current_grating = self._safe_query(
        self.get_device_parameter, "Spec", "Grating"
    )
    self.snapshot.current_blaze = self._safe_query(
        self.get_device_parameter, "Spec", "Blaze"
    )
    self.snapshot.current_ruling = self._safe_query(
        self.get_device_parameter, "Spec", "Ruling"
    )
    self.snapshot.current_exit_mirror = self._safe_query(
        self.get_device_parameter, "Spec", "Exit Mirror"
    )
    self.snapshot.current_turret = self._safe_query(
        self.get_device_parameter, "Spec", "Turret"
    )
    self.snapshot.current_slit_width = self._safe_query(
        self.get_device_parameter, "Spec", "Slit Width"
    )
    self.snapshot.current_spectrograph_shutter = self._safe_query(
        self.get_device_parameter, "Spec", "Shutter"
    )
    self.snapshot.current_focus_mirror = self._safe_query(
        self.get_device_parameter, "Spec", "Focus Mirror"
    )
    self.snapshot.current_side_entry_iris = self._safe_query(
        self.get_device_parameter, "Spec", "Side Entry Iris"
    )
    self.snapshot.current_delay_trig_mode = self._safe_query(
        self.get_device_parameter, "Del", "Trig. Mode"
    )
    self.snapshot.current_delay_repetition_rate = self._safe_query(
        self.get_device_parameter, "Del", "Repetition Rate"
    )
    self.snapshot.current_delay_setting = self._safe_query(
        self.get_device_parameter, "Del", "Setting"
    )
    self.snapshot.current_delay_a = self._safe_query(
        self.get_device_parameter, "Del", "Delay A"
    )
    self.snapshot.current_delay_b = self._safe_query(
        self.get_device_parameter, "Del", "Delay B"
    )
    self.snapshot.current_delay_c = self._safe_query(
        self.get_device_parameter, "Del", "Delay C"
    )
    self.snapshot.current_delay_d = self._safe_query(
        self.get_device_parameter, "Del", "Delay D"
    )
    self.snapshot.current_delay_e = self._safe_query(
        self.get_device_parameter, "Del", "Delay E"
    )
    self.snapshot.current_delay_f = self._safe_query(
        self.get_device_parameter, "Del", "Delay F"
    )
    self.snapshot.current_delay_g = self._safe_query(
        self.get_device_parameter, "Del", "Delay G"
    )
    self.snapshot.current_delay_h = self._safe_query(
        self.get_device_parameter, "Del", "Delay H"
    )
    self.snapshot.current_delay_ss_trigger = self._safe_query(
        self.get_device_parameter, "Del", "Ss Trigger"
    )
    self.snapshot.current_delay_burst_mode = self._safe_query(
        self.get_device_parameter, "Del", "Burst Mode"
    )
    self.snapshot.current_delay_manual_control = self._safe_query(
        self.get_device_parameter, "Del", "Man.Ctrl"
    )
