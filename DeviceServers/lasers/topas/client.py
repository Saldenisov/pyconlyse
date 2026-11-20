"""Bounded WinTopas4 requests; no implicit hardware commands or write retries."""
import math
import re
import time

import requests


class TopasError(RuntimeError):
    pass


class OutcomeUnknown(TopasError):
    """A write may have reached the server. Do not replay it automatically."""


def finite_number(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number')
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name} must be a finite number') from None
    if not math.isfinite(result):
        raise ValueError(f'{name} must be a finite number')
    return result


class TopasClient:
    def __init__(self, host, port, serial, timeout_s=2.0, session=None):
        if not isinstance(host, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host):
            raise ValueError('Use a hostname or IPv4 address without a URL or path')
        if not isinstance(serial, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', serial):
            raise ValueError('An explicit TOPAS serial number is required')
        if isinstance(port, bool) or int(port) != float(port) or not 1 <= int(port) <= 65535:
            raise ValueError('Invalid REST API port')
        self.timeout = finite_number(timeout_s, 'Request timeout')
        if not .1 <= self.timeout <= 10:
            raise ValueError('Request timeout must be between 0.1 and 10 seconds')
        self.base_url = f'http://{host}:{int(port)}/{serial}/v0/PublicAPI'
        self.serial = serial
        self.session = session if session is not None else requests.Session()
        self.session.trust_env = False

    def close(self):
        self.session.close()

    def _request(self, method, path, value=None):
        options = dict(timeout=(self.timeout, self.timeout), allow_redirects=False)
        if method != 'GET':
            options['json'] = value
        try:
            response = self.session.request(method, self.base_url + path, **options)
        except requests.RequestException as exc:
            error = f'WinTopas4 {method} {path}: {exc}'
            if method != 'GET':
                raise OutcomeUnknown(error + '; outcome unknown; verify device before retrying') from exc
            raise TopasError(error) from exc
        if not 200 <= response.status_code < 300:
            message = f'WinTopas4 {method} {path}: HTTP {response.status_code}: {response.text[:500]}'
            # Server-side failures can occur after a hardware command was accepted.
            if method != 'GET' and response.status_code >= 500:
                raise OutcomeUnknown(message + '; outcome unknown; verify device before retrying')
            raise TopasError(message)
        if not response.content.strip():
            return None
        try:
            return response.json()
        except ValueError as exc:
            error = OutcomeUnknown if method != 'GET' else TopasError
            raise error(f'WinTopas4 {method} {path}: invalid JSON response') from exc

    def read_core(self):
        output = self._request('GET', '/Optical/WavelengthControl/Output')
        shutter = self._request('GET', '/ShutterInterlock/State')
        auth = self._request('GET', '/Authentication/AuthenticationStatus')
        if not all(isinstance(v, dict) for v in (output, shutter, auth)):
            raise TopasError('Incomplete WinTopas4 status response')
        for data, names in ((output, ('IsWavelengthSettingInProgress', 'IsWaitingForUserAction', 'IsWavelengthStrict')),
                            (shutter, ('IsShutterOpen', 'IsInterlockOpen')),
                            (auth, ('CallerHasAccess',))):
            if any(type(data.get(name)) is not bool for name in names):
                raise TopasError('Invalid or missing WinTopas4 status flags')
        finite_number(output.get('Wavelength'), 'Reported wavelength')
        return {'output': output, 'shutter': shutter, 'authentication': auth}

    def read_snapshot(self):
        result = self.read_core()
        interactions = self._request('GET', '/Optical/WavelengthControl/ExpandedInteractions')
        motors = self._request('GET', '/Motors/AllProperties')
        if not isinstance(interactions, list) or not isinstance(motors, dict) or not isinstance(motors.get('Motors'), list):
            raise TopasError('Invalid WinTopas4 interactions or motors response')
        return {**result, 'interactions': interactions, 'motors': motors['Motors'], 'serial_number': self.serial}

    @staticmethod
    def _authorize(state):
        if not state['authentication']['CallerHasAccess']:
            raise TopasError('WinTopas4 has not authorized this host; use the vendor authentication procedure')
        if state['authentication'].get('AuthenticationHardwareFailure'):
            raise TopasError('WinTopas4 reports authentication hardware failure')

    def set_wavelength(self, wavelength_nm, interaction=None):
        wavelength = finite_number(wavelength_nm, 'Wavelength')
        if wavelength <= 0:
            raise ValueError('Wavelength must be positive')
        state = self.read_snapshot()
        self._authorize(state)
        if state['output']['IsWavelengthSettingInProgress'] or state['output']['IsWaitingForUserAction']:
            raise TopasError('TOPAS is already tuning or waiting for operator actions')
        candidates = [v for v in state['interactions'] if interaction is None or v.get('Type') == interaction]
        if not any(finite_number(v.get('OutputRange', {}).get('From'), 'Range start') <= wavelength
                   <= finite_number(v.get('OutputRange', {}).get('To'), 'Range end') for v in candidates):
            raise ValueError('Requested wavelength is outside the calibrated interaction ranges')
        # Preserve vendor separation, shutter and operator-message safeguards.
        response = self._request('PUT', '/Optical/WavelengthControl/SetWavelength', {
            'Wavelength': wavelength, 'Interaction': interaction or '*',
            'IgnoreSeparation': False, 'DontTouchShutterOnInteractionChange': False, 'SetForBackground': False,
        })
        if not isinstance(response, dict) or type(response.get('IsSuccess')) is not bool:
            raise OutcomeUnknown('WinTopas4 did not confirm whether wavelength setting was accepted')
        if not response['IsSuccess']:
            if response.get('FailedAfterInteractionSelection'):
                raise OutcomeUnknown(response.get('ErrorMessage') or 'TOPAS failed after selecting an interaction; verify optics')
            raise TopasError(response.get('ErrorMessage') or 'WinTopas4 rejected wavelength setting')
        return response

    def set_shutter(self, opened):
        if type(opened) is not bool:
            raise ValueError('Shutter selection must be boolean')
        state = self.read_core()
        self._authorize(state)
        if opened and (state['shutter']['IsInterlockOpen']
                       or state['shutter'].get('IsShutterTemporarilyClosedDueSafetyReasons')
                       or state['output']['IsWavelengthSettingInProgress']
                       or state['output']['IsWaitingForUserAction']):
            raise TopasError('Cannot open shutter while interlock is open, tuning, or operator actions are pending')
        self._request('PUT', '/ShutterInterlock/OpenCloseShutter', opened)
        # The vendor accepts the command before its shutter feedback changes.
        # Poll feedback only; never replay the PUT while waiting for motion.
        deadline = time.monotonic() + 2.0
        while True:
            try:
                actual = self._request('GET', '/ShutterInterlock/IsShutterOpen')
            except TopasError as exc:
                raise OutcomeUnknown('TOPAS shutter verification unavailable after the command; '
                                     'command was sent once; verify shutter before retrying') from exc
            if type(actual) is not bool:
                raise OutcomeUnknown('TOPAS returned invalid shutter readback after the command; '
                                     'command was sent once; verify shutter before retrying')
            if actual == opened:
                return actual
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OutcomeUnknown(
                    f'TOPAS shutter readback is {"open" if actual else "closed"}; '
                    f'requested {"open" if opened else "closed"} was not confirmed within 2.0 s. '
                    'Command was sent once; check TOPAS interlock and shutter before retrying')
            time.sleep(min(.1, remaining))

    def confirm_user_actions(self):
        state = self.read_core()
        self._authorize(state)
        if not state['output']['IsWaitingForUserAction']:
            raise TopasError('No TOPAS operator actions are awaiting confirmation')
        return self._request('PUT', '/Optical/WavelengthControl/FinishWavelengthSettingAfterUserActions',
                             {'RestoreShutter': False})

    def stop_motors(self):
        self._authorize(self.read_core())
        return self._request('POST', '/Motors/StopAll')

    def set_motor_position(self, motor_id, position, units='units'):
        if type(motor_id) is not int or motor_id < 0 or units not in {'units', 'steps'}:
            raise ValueError('Supply a motor index and units or steps')
        target = finite_number(position, 'Motor target')
        state = self.read_snapshot()
        self._authorize(state)
        if state['output']['IsWavelengthSettingInProgress'] or state['output']['IsWaitingForUserAction']:
            raise TopasError('Finish TOPAS wavelength setting before adjusting individual motors')
        motor = next((v for v in state['motors'] if v.get('Index') == motor_id), None)
        if motor is None or motor.get('IsFrozen') or motor.get('IsHoming'):
            raise TopasError('TOPAS motor is unavailable, frozen or homing')
        scale = finite_number(motor.get('Factor'), 'Motor unit scale') * 2 ** int(motor['StepDivision'])
        if scale == 0:
            raise TopasError('TOPAS motor has no valid unit conversion')
        if units == 'steps':
            if target != int(target) or not 0 <= target <= finite_number(motor.get('MaximalPosition'), 'Motor maximum'):
                raise ValueError('Motor steps are outside the configured travel')
            physical = target / scale + float(motor['Affix'])
        else:
            if not finite_number(motor.get('MinimalPositionInUnits'), 'Motor minimum') <= target <= finite_number(motor.get('MaximalPositionInUnits'), 'Motor maximum'):
                raise ValueError('Motor target is outside the configured travel')
            physical = target
        for forbidden in motor.get('ForbiddenRanges', []):
            if forbidden.get('IsEnabled') and float(forbidden['From']) <= physical <= float(forbidden['To']):
                raise ValueError('Motor target is inside a vendor-configured forbidden range')
        path = '/Motors/TargetPosition' + ('InUnits' if units == 'units' else '') + f'?id={motor_id}'
        self._request('PUT', path, target)
        actual = finite_number(self._request('GET', path), 'Motor target readback')
        tolerance = abs(1 / scale) + 1e-9 if units == 'units' else .1
        if not math.isclose(actual, target, rel_tol=0, abs_tol=tolerance):
            raise TopasError('TOPAS did not confirm the motor target; inspect motor readback')
        return {'motor_id': motor_id, 'target': actual, 'units': units}
