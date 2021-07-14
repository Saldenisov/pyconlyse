#!/usr/bin/env python
# -*- coding: utf-8 -*-


import time
import numpy

from tango import AttrQuality, AttrWriteType, DispLevel, DevState, DebugIt
from tango.test_context import DeviceTestContext, DeviceProxy
from tango.server import Device, attribute, command, pipe, device_property

import ctypes
from ximc import (lib, arch_type, ximc_dir, EnumerateFlags, get_position_t, Result,
                  controller_name_t, status_t, set_position_t, PositionFlags, status_t, device_information_t,
                  string_at)
from typing import Dict, Tuple
from pathlib import Path
from time import sleep


class DS_STANDA_STEP_MOTOR(Device):
    """"
    Device Server (Tango) which controls the Standa motorized equipment using libximc.dll
    """
    POWER_STATES = {0: 'PWR_UNKNOWN', 1: 'PWR_OFF', 3: 'PWR_NORM', 4: 'PWR_REDUCED',5: 'PWR_MAX'}

    position = attribute(label="Position", dtype=float,
                         display_level=DispLevel.OPERATOR,
                         access=AttrWriteType.READ_WRITE,
                         unit="step", format="8.4f",
                         doc="the position of axis",
                         polling_period=100,
                         min_value='-100.0', max_value='100.0')

    @attribute(label='Temperature', access=AttrWriteType.READ, display_level=DispLevel.OPERATOR, unit='deg',
               polling_period=100, doc="Temperature in tenths of degrees C.")
    def temperature(self):
        return self.__temperature

    @attribute(label='Power current', access=AttrWriteType.READ, display_level=DispLevel.OPERATOR, unit='mA',
               polling_period=100)
    def power_current(self):
        return self.__power_current

    @attribute(label='Power voltage', access=AttrWriteType.READ, display_level=DispLevel.OPERATOR, unit='V',
               polling_period=100)
    def power_voltage(self):
        return self.__power_voltage

    @attribute(label='Power status', access=AttrWriteType.READ, dtype=str, display_level=DispLevel.OPERATOR,
               polling_period=100)
    def power_status(self):
        return self.__power_status

    uri = attribute(label="URI", dtype=str,
                    display_level=DispLevel.OPERATOR,
                    access=AttrWriteType.READ,
                    doc="the URI of axis")

    device_id_internal = attribute(label="internal ID of axis", dtype=int,
                                   display_level=DispLevel.EXPERT,
                                   access=AttrWriteType.READ,
                                   doc="The STANDA dll enumerates the devices, so it is important to know the "
                                       "device`s number, that dll has given to it.")


    @pipe(label="DS Info")
    def info(self):
        return 'Information', dict(manufacturer='STANDA', model='XXX', version_number=0.1, device_id=self.device_id)

    ip_address = device_property(dtype=str, default_value='10.20.30.204')
    device_id = device_property(dtype=str, default_value='00003D73')
    friendly_name = device_property(dtype=str)
    wait_time = device_property(dtype=int, default_value=5)

    def init_device(self):
        Device.init_device(self)
        self.__position = 0.0
        self.__device_id_internal = -1
        self.__temperature = 25
        self.__power_current = 0
        self.__power_voltage= 0
        self.__power_status = self.POWER_STATES[0]

        device_id_internal_seq, self.__uri = self.find_device()

        if device_id_internal_seq >= 0:
            self.info_stream(f"STANDA Device with ID {self.device_id} was found.")
            self.set_state(DevState.STANDBY)
        else:
            self.info_stream(f"STANDA Device with ID {self.device_id} was NOT found.")
            self.set_state(DevState.FAULT)

    def device_name(self) -> str:
        return f'Device {self.device_id} {self.friendly_name}'

    def check_func_allowance(self, func) -> int:
        rules = {'write_position': [DevState.ON],
                 'define_position': [DevState.ON],
                 'turn_on': [DevState.OFF, DevState.FAULT, DevState.STANDBY],
                 'turn_off': [DevState.ON],
                 'move_axis': [DevState.ON],
                 'stop_axis': [DevState.MOVING, DevState.ON],
                 'find_device': [DevState.OFF, DevState.FAULT, DevState.STANDBY],
                 'get_controller_status': [DevState.ON, DevState.MOVING]}
        state_ok = -1
        if func.__name__ in rules:
            rules_for_func = rules[func.__name__]
            if self.get_state() not in rules_for_func:
                state_ok = 1
        return state_ok

    def find_device(self) -> int:
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            self.info_stream(f"Searching for STANDA device {self.device_id}")
            lib.set_bindy_key(str(Path(ximc_dir / arch_type / "keyfile.sqlite")).encode("utf-8"))
            # Enumerate devices
            probe_flags = EnumerateFlags.ENUMERATE_PROBE + EnumerateFlags.ENUMERATE_NETWORK
            enum_hints = f"addr={self.ip_address}".encode('utf-8')
            # enum_hints = b"addr=" # Use this hint string for broadcast enumerate
            devenum = lib.enumerate_devices(probe_flags, enum_hints)
            device_counts = lib.get_device_count(devenum)
            sleep(0.05)
            if device_counts > 0:
                for device_id_internal_seq in range(device_counts):
                    uri = lib.get_device_name(devenum, device_id_internal_seq)
                    sleep(0.01)
                    if self.device_id in uri.decode('utf-8'):
                        return device_id_internal_seq, uri
        return argreturn

    def read_position(self):
        state_ok = self.check_func_allowance(self.read_position)
        if state_ok:
            pos = get_position_t()
            result = lib.get_position(self.__device_id_internal, ctypes.byref(pos))
            if result == Result.Ok:
                pos_microsteps = pos.Position * 256 + pos.uPosition
                pos_basic_units = pos_microsteps / 256
                self.__position = pos_basic_units
            else:
                self.error_stream(f'Could not read position of {self.device_name()}')
        else:
            self.error_stream(f'Could not read position of {self.device_name()}')
        return self.__position

    def read_uri(self):
        return self.__uri

    def read_device_id_internal(self):
        return self.__device_id_internal

    def write_device_id_internal(self, device_id_internal):
        self.__device_id_internal = device_id_internal

    def write_position(self, pos):
        self.debug_stream(f'Setting position {pos} of {self.device_name()}.')
        state_ok = self.check_func_allowance(self.write_position)
        if state_ok:
            # TODO: range check
            self.move_axis(pos)

    def _standa_error(self, error: int) -> Tuple[bool, str]:
        # TODO: finish filling different errors values
        if error == 0:
            res, comments = True, ''
        elif error == -1:
            res, comments = False, 'Standa: generic error.'
        else:
            res, comments = False, 'Standa: unknown error.'

        return res, comments

    #Commands
    @command
    def define_position(self, position):
        self.debug_stream(f'Setting position {position} of {self.device_name()}.')
        state_ok = self.check_func_allowance(self.write_position)
        if state_ok:
            # TODO: range check
            pos_steps = int(position // 1)
            pos_microsteps = int(position % 1 * 256)
            pos_standa = set_position_t()
            pos_standa.Position = ctypes.c_int(pos_steps)
            pos_standa.uPosition = ctypes.c_int(pos_microsteps)
            pos_standa.EncPosition = ctypes.c_longlong(0)
            pos_standa.PosFlags = ctypes.c_uint(PositionFlags.SETPOS_IGNORE_ENCODER)
            lib.set_position(self.__device_id_internal, ctypes.byref(pos_standa))
            self.read_position()
        else:
            self.info_stream(f'Cannot write position, because {self.device_name()} state {self.get_state()} is wrong.')

    @command
    def turn_on(self):
        self.debug_stream(f"Turning on device {self.device_id} {self.friendly_name}.")
        state_ok = self.check_func_allowance(self.turn_on)
        if state_ok:
            self.__device_id_internal = lib.open_device(self.__uri)
            if self.__device_id_internal >= 0:
                self.set_state(DevState.ON)
                self.debug_stream(f"Device {self.device_id} {self.friendly_name} WAS turned on.")
                self.read_position()
            else:
                self.set_state(DevState.FAULT)
                self.error_stream(f"Could NOT turn on {self.device_name()}.")
        else:
            self.error_stream(f"Could NOT turn on {self.device_name()}. State is {self.state}")

    @command
    def turn_off(self):
        self.debug_stream(f"Turning off device {self.device_id} {self.friendly_name}.")
        state_ok = self.check_func_allowance(self.turn_on)
        if state_ok:
            arg = ctypes.cast(self.__device_id_internal, ctypes.POINTER(ctypes.c_int))
            result = lib.close_device(ctypes.byref(arg))
            self.debug_stream(f'Success of turn off for {self.device_name()} was {result}.')
            sleep(0.05)
            if result == 0:
                self.set_state(DevState.OFF)
                self.__device_id_internal = -1
            else:
                self.set_state(DevState.FAULT)
        else:
            self.error_stream(f"Could NOT turn off {self.device_name()}. State is {self.state}")

    @command(dtype_in=float, doc_in="Takes pos of axis in float.")
    def move_axis_abs(self, pos):
        self.move_axis_standa(pos)

    @command(dtype_in=float, doc_in="Takes rel pos of axis in float.")
    def move_axis_rel(self, rel_pos):
        self.move_axis_standa(self.__position + rel_pos)

    def move_axis(self, pos):
        pos = float(pos)
        self.debug_stream(f"Moving axis of device {self.device_id} {self.friendly_name}.")
        state_ok = self.check_func_allowance(self.move_axis)
        if state_ok:
            # TODO: add range check
            microsteps = int(pos % 1 * 256)
            steps = int(pos // 1)
            result = lib.command_move(self.__device_id_internal, steps, microsteps)
            if result == Result.Ok:
                result = lib.command_wait_for_stop(self.__device_id_internal, self.wait_time)

            if result != Result.Ok:
                self.error_stream(f'Move command for {self.device_name()} did not work {result}.')

            self.read_position()

    @command
    def stop_movement(self):
        self.debug_stream(f"Stoping axis movement of device {self.device_id} {self.friendly_name}.")
        state_ok = self.check_func_allowance(self.move_axis_abs)
        if state_ok:
            result = lib.command_stop(self.__device_id_internal)
            if result == 0:
                self.state = DevState.ON
                self.info_stream(f"Axis movement of device {self.device_id} {self.friendly_name} was stopped.")
            else:
                self.error_stream(f"Axis movement of device {self.device_id} {self.friendly_name} was NOT stopped.")
            self.get_controller_status()

    @command(polling_period=100)
    def get_controller_status(self):
        state_ok = self.check_func_allowance(self.get_controller_status)
        if state_ok:
            x_status = status_t()
            result = lib.get_status(self.__device_id_internal, ctypes.byref(x_status))
            if result == Result.Ok:
                self.__temperature = x_status.CurT / 10.0
                self.__power_current = x_status.Ipwr
                self.__power_voltage = x_status.Upwr / 100.0
                self.__power_status = self.POWER_STATES[x_status.PWRSts]

            # TODO: add check status if connected or not


class Standa_minimum():

    ip_address = '10.20.30.204'
    device_id = '00003D6A'
    wait_time = 5
    state = DevState.ON


    def __init__(self):
        self.__position = 0.0
        self.__device_id_internal_seq, self.__uri = self.find_device()
        self.__device_id_internal = -1
        print(f'Device_id_internal_seq: {self.__device_id_internal_seq}, URI: {self.__uri}')

    def check_func_allowance(self, func) -> int:
        rules = {'write_position': [DevState.ON],
                 'turn_on': [DevState.OFF, DevState.FAULT, DevState.STANDBY],
                 'turn_off': [DevState.ON],
                 'move_axis': [DevState.ON],
                 'stop_axis': [DevState.MOVING, DevState.ON],
                 'find_device': [DevState.OFF, DevState.FAULT, DevState.STANDBY]}
        state_ok = -1
        name = func.__name__
        if name in rules:
            rules_for_func = rules[func.__name__]
            if self.state not in rules_for_func:
                state_ok = 1
        return state_ok

    def device_name(self) -> str:
        return f'Device {self.device_id} {self.friendly_name}'

    def find_device(self) -> int:
        lib.set_bindy_key(str(Path(ximc_dir / arch_type / "keyfile.sqlite")).encode("utf-8"))
        # Enumerate devices
        probe_flags = EnumerateFlags.ENUMERATE_PROBE + EnumerateFlags.ENUMERATE_NETWORK
        enum_hints = f"addr={self.ip_address}".encode('utf-8')
        # enum_hints = b"addr=" # Use this hint string for broadcast enumerate
        self.devenum = lib.enumerate_devices(probe_flags, enum_hints)
        device_counts = lib.get_device_count(self.devenum)
        sleep(0.05)
        argreturn = -1, ''
        if device_counts > 0:
            for device_id_internal_seq in range(device_counts):
                uri = lib.get_device_name(self.devenum, device_id_internal_seq)
                sleep(0.01)
                if self.device_id in uri.decode('utf-8'):
                    return device_id_internal_seq, uri
            return argreturn
        else:
            return argreturn

    def read_position(self):
        pos = get_position_t()
        a = self.__device_id_internal
        result = lib.get_position(self.__device_id_internal, ctypes.byref(pos))
        if result == Result.Ok:
            pos_microsteps = pos.Position * 256 + pos.uPosition
            pos_basic_units = pos_microsteps / 256
            self.__position = pos_basic_units
        return self.__position

    def test_info(self):
        print("\nGet device info")
        x_device_information = device_information_t()
        result = lib.get_device_information(self.__device_id_internal, ctypes.byref(x_device_information))
        print("Result: " + repr(result))
        if result == Result.Ok:
            print("Device information:")
            print(" Manufacturer: " +
                  repr(string_at(x_device_information.Manufacturer).decode()))
            print(" ManufacturerId: " +
                  repr(string_at(x_device_information.ManufacturerId).decode()))
            print(" ProductDescription: " +
                  repr(string_at(x_device_information.ProductDescription).decode()))
            print(" Major: " + repr(x_device_information.Major))
            print(" Minor: " + repr(x_device_information.Minor))
            print(" Release: " + repr(x_device_information.Release))

    def turn_on(self):
        self.__device_id_internal = lib.open_device(self.__uri)
        print(f'Turn on result: {self.__device_id_internal}')
        if self.__device_id_internal >= 0:
            self.read_position()

    def turn_off(self):
        arg = ctypes.cast(self.__device_id_internal, ctypes.POINTER(ctypes.c_int))
        r = lib.close_device(ctypes.byref(arg))
        sleep(0.05)
        print(f'Turn off result: {r}')

    def move_axis(self, pos):
        state_ok = self.check_func_allowance(self.move_axis)
        if state_ok:
            # TODO: add range check
            microsteps_set = 256
            microsteps = int(pos % 1 * microsteps_set)
            steps = int(pos // 1)
            result = lib.command_move(self.__device_id_internal, steps, microsteps)
            if result == Result.Ok:
                result = lib.command_wait_for_stop(self.__device_id_internal, self.wait_time)

            if result != Result.Ok:
                self.error_stream(f'Move command for {self.device_name()} did not work {result}.')

            self.read_position()

    def write_position(self, position):
        state_ok = self.check_func_allowance(self.write_position)
        if state_ok:
            pos_steps = int(position // 1)
            pos_microsteps = int(position % 1 * 256)
            pos_standa = set_position_t()
            pos_standa.Position = ctypes.c_int(pos_steps)
            pos_standa.uPosition = ctypes.c_int(pos_microsteps)
            pos_standa.EncPosition = ctypes.c_longlong(0)
            pos_standa.PosFlags = ctypes.c_uint(PositionFlags.SETPOS_IGNORE_ENCODER)
            lib.set_position(self.__device_id_internal, ctypes.byref(pos_standa))
            self.read_position()
        else:
            self.info_stream(f'Cannot write position, because {self.device_name()} state {self.get_state()} is wrong.')

if __name__ == "__main__":
    DS_STANDA_STEP_MOTOR.run_server()
    # a = Standa_minimum()
    # a.turn_on()
    # a.test_info()
    # a.state = DevState.ON
    # a.write_position(0)
    # a.move_axis(10.12)
    # a.move_axis(0)
    # a.turn_off()
