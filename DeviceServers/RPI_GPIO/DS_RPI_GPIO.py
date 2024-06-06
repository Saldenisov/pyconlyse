#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
import cv2
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from typing import Union, List
from gpiozero.pins.pigpio import PiGPIOFactory
from gpiozero import LED
import zmq
from DeviceServers.General.DS_GPIO import DS_GPIO, OrderPulsesInfo, MyPin
# -----------------------------
from functools import partial
from tango import DevState
from threading import Thread
from time import sleep

from utilities.myfunc import ping, get_random_string


class DS_RPI_GPIO(DS_GPIO):
    _version_ = '0.1'
    _model_ = 'RPI GPIO controller'
    RULES = {**DS_GPIO.RULES}

    def init_device(self):
        super().init_device()
        self.turn_on()
        self.register_variables_for_archive()
        self.get_pins_states()
        self.get_pin_state(4)

    def find_device(self):
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            if ping(self.ip_address):
                self.set_state(DevState.INIT)
                self._device_id_internal, self._uri = int(self.device_id), self.friendly_name.encode('utf-8')
                states = []
                for pins_param in self.parameters['Pins']:
                    pin_number = pins_param[0]
                    mypin = MyPinRPI(pin_number=pin_number, parameters=pins_param[1:], ip_address=self.ip_address,
                                     parent=self)
                    self.pins[pins_param[0]] = mypin
                    self.set_pin_state_local([pin_number, pins_param[3]])
                    states.append(mypin.value)
                self._states = states
            else:
                self._device_id_internal, self._uri = argreturn

    def get_pins_states(self):
        states = []
        for pin in self._pin_ids:
            control_pin = self.pins[pin]
            value = control_pin.value
            states.append(value)
        self._states = states

    def register_variables_for_archive(self):
        super().register_variables_for_archive()
        extra = {}
        for pin in self._pin_ids:
            archive_key = f'pin_state_{pin}'
            extra[archive_key] = (partial(self.value_from_pin, pin), 'uint8')
        self.archive_state.update(extra)

    def value_from_pin(self, pin_id: int):
        control_pin = self.pins[pin_id]
        return control_pin.value

    def get_pin_state_local(self, pin_id: int) -> Union[int, str]:
        if pin_id in self.pins:
            value = self.pins[pin_id].value
            return value
        else:
            return f'Wrong pin id {pin_id} was given.'

    def set_pin_state_local(self, pin_id_value: List[int]) -> Union[int, str]:
        pin_id = pin_id_value[0]
        pin_value = int(pin_id_value[1])
        if pin_id in self.pins:
            if pin_value >= 1:
                self.pins[pin_id].on()
            elif pin_value <= 0:
                self.pins[pin_id].off()
            return 0
        else:
            return f'Wrong pin id {pin_id} was given.'

    def generate_pulses_local(self, order: OrderPulsesInfo):
        pin: MyPinRPI = self.pins[order.pin]
        pin.generate_TTL(order)

    def generate_TTL(self, pin: int, dt: int, time_delay: int):
        self.pins[pin].toggle()

    def get_controller_status_local(self) -> Union[int, str]:
        res = DS_GPIO.check_ip(self.ip_address)
        if res:
            self.set_state(DevState.ON)
            self.get_pins_states()
            return 0
        else:
            self.turn_on_local()
            res = DS_GPIO.check_ip(self.ip_address)
            if res:
                self.set_state(DevState.ON)
                self.get_pins_states()
                return 0
            else:
                self.set_state(DevState.FAULT)
                return f'Could not turn on, RPI {self.ip_address} is away...'

    def turn_on_local(self) -> Union[int, str]:
        if ping(self.ip_address):
            self.set_state(DevState.ON)
            return 0
        else:
            self.set_state(DevState.FAULT)
            return f'Could not turn on, RPI {self.ip_address} is away...'

    def turn_off_local(self) -> Union[int, str]:
        for pin in self.pins.values():
            pin.stop()
        self.set_state(DevState.OFF)


class MyPinRPI(MyPin):
    def __init__(self, pin_number: int, parameters: tuple, ip_address: str, parent: DS_RPI_GPIO):
        """
        parameters ('LED', 'Laser_shutter', 0, 'gpiozero')
        or
        parameters ('LED', 'step_A4988_5th', 0, 'zmq')
        """
        self.pin_number = pin_number
        self.ip_address = ip_address
        self.pin_type: str = None
        self._stop = False
        self._alive = True
        self.state = 0
        self.order = None
        if parameters[3] == 'gpiozero':
            self.pin_type = 'gpiozero'
            factory = PiGPIOFactory(host=self.ip_address)
            self.pin: LED = eval(parameters[0])(pin=self.pin_number, pin_factory=factory)
            self.on = self.pin.on
            self.off = self.pin.off
            self.toggle = self.pin.toggle
            self.generate_TTL = partial(self.generate_TTL_gpiozero, self)
        elif parameters[3] == 'zmq':
            self.pin_type = 'zmq'
            dealer, subscriber, poller, context = self.create_sockets()
            self.connect_socket(dealer, subscriber)
            self.on = self.on_zmq
            self.off = self.off_zmq
            self.toggle = self.toggle_zmq
            self.generate_TTL = self.generate_TTL_zmq
            thread_zmq = Thread(target=self.receive_msg)
            thread_zmq.start()

    def on_zmq(self):
        """
        msg is utf string dict{cmd: str, order_id: str, pin_number: int, etc}
        """
        msg = {'cmd': 'ON', 'order_id': get_random_string(10), 'pin_number': self.pin_number}
        msg = str(msg)
        self.send_msg(msg)

    def off_zmq(self):
        """
        msg is utf string dict{cmd: str, order_id: str, pin_number: int, etc}
        """
        msg = {'cmd': 'OFF', 'order_id': get_random_string(10), 'pin_number': self.pin_number}
        msg = str(msg)
        self.send_msg(msg)

    def toggle_zmq(self):
        """
        msg is utf string dict{cmd: str, order_id: str, pin_number: int, etc}
        """
        msg = {'cmd': 'TOGGLE', 'order_id': get_random_string(10), 'pin_number': self.pin_number}
        msg = str(msg)
        self.send_msg(msg)

    def ttl_done_zmq(self):
        msg = {'cmd': 'GET_TTL', 'order_id': get_random_string(10), 'pin_number': self.pin_number}
        msg = str(msg)
        self.send_msg(msg)

    def ttl_stop_zmq(self):
        msg = {'cmd': 'STOP', 'order_id': get_random_string(10), 'pin_number': self.pin_number}
        msg = str(msg)
        self.send_msg(msg)

    def value_zmq(self):
        """
        msg is utf string dict{cmd: str, order_id: str, pin_number: int, etc}
        """
        msg = {'cmd': 'VALUE', 'order_id': get_random_string(10), 'pin_number': self.pin_number}
        msg = str(msg)
        self.send_msg(msg)
        sleep(0.05)
        return self.state

    def ttl_zmq(self, order: OrderPulsesInfo):
        """
        msg is utf string dict{cmd: str, order_id: str, pin_number: int, etc}
        """
        msg = {'cmd': 'TTL', 'order_id': get_random_string(10), 'pin_number': self.pin_number,
               'number_ttl': order.number_of_pulses, 'delay': order.time_delay, 'width': order.dt}
        msg = str(msg)
        self.send_msg(msg)

    def generate_TTL_zmq(self, order: OrderPulsesInfo):
        self.ttl_zmq(order)
        self.order = order
        while True:
            sleep(0.25)
            self.ttl_done_zmq()
            if order.order_done:
                self.ttl_stop_zmq()
                break

    def stop(self):
        if self.pin_type == 'zmq':
            self._stop = True
            sleep(0.1)
            self.dealer.close()
            self.poller.close()
            self.context.term()
        elif self.pin_type == 'gpiozero':
            self.pin.close()

    def on(self):
        pass

    def off(self):
        pass

    def toggle(self):
        pass

    def generate_TTL(self, order: OrderPulsesInfo):
        pass

    def generate_TTL_gpiozero(self, order: OrderPulsesInfo):
        for i in range(order.number_of_pulses):
            self.toggle()
            order.pulses_done += 1
            if order.order_done:
                break

    @property
    def value(self):
        if self.pin_type == 'gpiozero':
            return self.pin.value
        elif self.pin_type == 'zmq':
            return self.value_zmq()

    def create_sockets(self):
        context = zmq.Context()
        dealer: zmq.DEALER = context.socket(zmq.DEALER)
        dealer.setsockopt_unicode(zmq.IDENTITY, f'{get_random_string(5)}')
        subscriber = context.socket(zmq.SUB)
        subscriber.setsockopt(zmq.SUBSCRIBE, b'')
        # POLLER
        poller = zmq.Poller()
        poller.register(dealer, zmq.POLLIN)
        poller.register(subscriber, zmq.POLLIN)
        self.dealer = dealer
        self.subscriber = subscriber
        self.poller = poller
        self.context = context
        return dealer, subscriber, poller, context

    def connect_socket(self, dealer: zmq.DEALER, subscriber: zmq.SUB):
        dealer.connect(f'tcp://{self.ip_address}:{5555}')
        subscriber.connect(f'tcp://{self.ip_address}:{5555 + 1}')

    def send_msg(self, msg: str):
        self.dealer.send_string(msg)

    def heartbeat(self):
        while not self._stop:
            sleep(2)
            if not self._alive:
                print(f'Heartbeat absent from RPI for pin {self.pin_number}.')
            else:
                self._alive = False

    def receive_msg(self):
        """
        cmd[0]:
        1 - TTL
        2 - STOP
        3 - GET_TTL
        4 - TOGGLE
        msg is utf string dict{cmd: str, order_id: str, pin_number: int, etc}
        """

        hb = Thread(target=self.heartbeat)
        hb.start()

        while not self._stop:
            msg = {}
            try:
                sockets = dict(self.poller.poll(10))
                if self.dealer in sockets:
                    msg: str = self.dealer.recv_multipart()[0]
                    msg = msg.decode('utf-8')
                    msg = eval(msg)
                    self.treat_msg(msg)
                elif self.subscriber in sockets:
                    msg: str = self.subscriber.recv_string()
                    self._alive = True
            except Exception as e:
                print(e)

    def treat_msg(self, msg):
        if msg:
            self.state = msg['state']
            if self.order:
                self.order.pulses_done = msg['ttl_done']
                self.order.state = msg['state']
                if self.order.number_of_pulses == self.order.pulses_done and not self.order.order_done:
                    self.order.order_done = True
                    print(f'Order {self.order.number_of_pulses} is done.')


if __name__ == "__main__":
    DS_RPI_GPIO.run_server()
