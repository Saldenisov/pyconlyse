"""Tango interface to WinTopas4; all hardware I/O belongs to its REST worker."""
import json
from pathlib import Path
import sys

from tango import AttrWriteType, DevState
from tango.server import Device, attribute, command, device_property

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from DeviceServers.lasers.topas.client import TopasClient, finite_number
from DeviceServers.lasers.topas.monitor import TopasMonitor


class DS_TOPAS(Device):
    api_host = device_property(dtype=str, default_value='127.0.0.1')
    api_port = device_property(dtype=int, default_value=8004)
    topas_serial = device_property(dtype=str, default_value='')
    timeout_s = device_property(dtype=float, default_value=2.0)
    poll_interval_s = device_property(dtype=float, default_value=1.0)
    stale_after_s = device_property(dtype=float, default_value=5.0)

    def init_device(self):
        super().init_device()
        self.monitor = None
        self.configuration_error = ''
        try:
            client = TopasClient(self.api_host, self.api_port, self.topas_serial, self.timeout_s)
            self.monitor = TopasMonitor(client, self.poll_interval_s, self.stale_after_s)
            self.monitor.start()
            self.set_state(DevState.INIT)
            self.set_status('Waiting for WinTopas4 status; startup sends GET requests only')
        except Exception as exc:
            self.configuration_error = str(exc)
            self.set_state(DevState.FAULT)
            self.set_status(self.configuration_error)

    def delete_device(self):
        if self.monitor:
            self.monitor.close()

    def always_executed_hook(self):
        if not self.monitor:
            return
        status = self.monitor.snapshot()
        if not status['fresh']:
            state, text = DevState.FAULT, status['read_error'] or 'TOPAS telemetry is unavailable or stale'
        elif status['outcome_unknown'] or (status['operation'] or {}).get('status') == 'failed':
            state, text = DevState.FAULT, (status['uncertain_operation'] or status['operation'] or {}).get('error') or 'Prior command outcome is unknown'
        else:
            data = status['data']
            output, shutter = data['output'], data['shutter']
            if data['authentication'].get('AuthenticationHardwareFailure'):
                state, text = DevState.FAULT, 'WinTopas4 reports authentication hardware failure'
            elif output['IsWaitingForUserAction']:
                state, text = DevState.STANDBY, 'TOPAS is waiting for operator actions; inspect messages_json'
            elif output['IsWavelengthSettingInProgress'] or (status['operation'] or {}).get('status') in {'queued', 'running'}:
                state, text = DevState.MOVING, 'TOPAS request or wavelength setting in progress'
            elif shutter['IsInterlockOpen'] or not data['authentication']['CallerHasAccess']:
                state, text = DevState.STANDBY, 'TOPAS interlock is open or this host is not authorized'
            elif shutter.get('IsShutterTemporarilyClosedDueSafetyReasons'):
                state, text = DevState.STANDBY, 'WinTopas4 has temporarily closed the shutter for safety'
            elif not data['motors'] or output.get('IsUndefined') or output['Wavelength'] <= 0:
                state, text = DevState.STANDBY, 'WinTopas4 has no available motors or calibrated output wavelength'
            else:
                state, text = DevState.ON, 'WinTopas4 API ready; shutter ' + ('Open' if shutter['IsShutterOpen'] else 'Closed')
        self.set_state(state)
        self.set_status(text)

    def _monitor(self):
        if self.monitor is None:
            raise RuntimeError(self.configuration_error or 'TOPAS monitor is unavailable')
        return self.monitor

    def _data(self):
        return self._monitor().require_fresh()

    @attribute(dtype=float, unit='nm', format='%.2f', access=AttrWriteType.READ_WRITE)
    def wavelength_nm(self):
        """Vendor output wavelength; a target while is_tuning is true."""
        return float(self._data()['output']['Wavelength'])

    def write_wavelength_nm(self, value):
        wavelength = finite_number(value, 'Wavelength')
        if wavelength <= 0:
            raise ValueError('Wavelength must be positive')
        self._monitor().submit('set_wavelength', wavelength)

    @attribute(dtype=bool, access=AttrWriteType.READ_WRITE)
    def shutter_open(self):
        return self._data()['shutter']['IsShutterOpen']

    def write_shutter_open(self, value):
        self._monitor().submit('set_shutter', bool(value))

    @attribute(dtype=str)
    def interaction(self):
        return str(self._data()['output'].get('Interaction', ''))

    @attribute(dtype=bool)
    def is_tuning(self):
        return self._data()['output']['IsWavelengthSettingInProgress']

    @attribute(dtype=bool)
    def waiting_for_user(self):
        return self._data()['output']['IsWaitingForUserAction']

    @attribute(dtype=bool)
    def interlock_open(self):
        return self._data()['shutter']['IsInterlockOpen']

    @attribute(dtype=bool)
    def caller_has_access(self):
        return self._data()['authentication']['CallerHasAccess']

    @attribute(dtype=float, unit='s')
    def telemetry_age_s(self):
        value = self._monitor().snapshot()['age_s']
        return -1.0 if value is None else value

    @attribute(dtype=str)
    def messages_json(self):
        return json.dumps(self._data()['output'].get('Messages', []))

    @attribute(dtype=str)
    def interactions_json(self):
        return json.dumps(self._data()['interactions'])

    @attribute(dtype=str)
    def motors_json(self):
        return json.dumps(self._data()['motors'])

    @attribute(dtype=str)
    def snapshot_json(self):
        return json.dumps(self._monitor().snapshot())

    @attribute(dtype=str)
    def operation_json(self):
        return json.dumps(self._monitor().snapshot()['operation'])

    @command(dtype_in=float, dtype_out=str)
    def SetWavelength(self, value):
        wavelength = finite_number(value, 'Wavelength')
        if wavelength <= 0:
            raise ValueError('Wavelength must be positive')
        return self._monitor().submit('set_wavelength', wavelength)

    @command(dtype_in=str, dtype_out=str)
    def SetWavelengthWithInteraction(self, value):
        selection = json.loads(value)
        if not isinstance(selection, dict) or set(selection) != {'wavelength_nm', 'interaction'}:
            raise ValueError('Supply wavelength_nm and interaction as a JSON object')
        wavelength = finite_number(selection['wavelength_nm'], 'Wavelength')
        if wavelength <= 0 or not isinstance(selection['interaction'], str) or not selection['interaction']:
            raise ValueError('Supply a positive wavelength and an explicit calibrated interaction')
        return self._monitor().submit('set_wavelength', wavelength, selection['interaction'])

    @command(dtype_out=str)
    def OpenShutter(self):
        return self._monitor().submit('set_shutter', True)

    @command(dtype_out=str)
    def CloseShutter(self):
        return self._monitor().submit('set_shutter', False)

    @command(dtype_out=str)
    def ConfirmUserActions(self):
        return self._monitor().submit('confirm_user_actions')

    @command(dtype_out=str)
    def Stop(self):
        """Request vendor StopAll; observe motors_json for actual motor state."""
        return self._monitor().submit('stop_motors')

    @command
    def Refresh(self):
        self._monitor().wake.set()

    @command
    def ClearError(self):
        """Explicit acknowledgement only; never retries a hardware operation."""
        self._monitor().clear_error()


if __name__ == '__main__':
    DS_TOPAS.run_server()
