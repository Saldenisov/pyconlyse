import logging
from abc import abstractmethod
from time import time, sleep
from typing import Union
from communication.logic.thinker import Thinker, ThinkerEvent
from communication.messaging.messages import MsgComExt, MessageExt
from communication.messaging.message_types import AccessLevel, Permission
from devices.datastruct_for_messaging import *

from communication.messaging.messengers import PUB_Socket, SUB_Socket, PUB_Socket_Server
from devices.devices import Server
from devices.service_devices.pdu.pdu_controller import PDUController
from devices.devices_dataclass import Connection
from utilities.myfunc import info_msg, error_logger
from utilities.errors.myexceptions import DeviceError

module_logger = logging.getLogger(__name__)


class GeneralCmdLogic(Thinker):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from communication.logic.logic_functions import internal_hb_logic
        self.register_event('heartbeat', internal_hb_logic, external_name=f'heartbeat:{self.parent.name}',
                            event_id=f'heartbeat:{self.parent.device_id}')
        self.timeout = int(self.parent.get_general_settings()['timeout'])
        self.connections = self.parent.messenger.connections

    def react_broadcast(self, msg: MessageExt):
        if msg.com == MsgComExt.HEARTBEAT.msg_name and msg.sender_id in self.connections:
            try:
                self.events[msg.info.event_id].time = time()
                self.events[msg.info.event_id].n = msg.info.event_n
                if self.parent.pyqtsignal_connected:
                    self.parent.signal.emit(msg.ext_to_int())
            except (KeyError, TypeError) as e:
                error_logger(self, self.react_broadcast, e)

    def react_external(self, msg: MessageExt):
        # TODO: add decision on permission
        if not msg.receiver_id and msg.com != MsgComExt.HEARTBEAT_FULL.msg_name:
            self.react_broadcast(msg)
        # When the message is dedicated to Device
        elif msg.sender_id in self.connections and msg.receiver_id == self.parent.device_id and not msg.forward_to:
            self.react_directed(msg)
        else:
            pass  # TODO: that I do not know what it is...add MsgError

    def react_directed(self, msg: MessageExt):
        if self.parent.pyqtsignal_connected:
            # Convert MessageExt to MessageInt and emit it
            msg_int = msg.ext_to_int()
            self.parent.signal.emit(msg_int)
        msg_r = None
        if msg.com == MsgComExt.DO_IT.msg_name:
            if not self.parent.add_to_executor(self.parent.execute_com, msg=msg):
                self.logger.error(f'Adding to executor {msg.info} failed.')
        elif msg.com == MsgComExt.DONE_IT.msg_name:
            info: Union[DoneIt, MsgError] = msg.info
            if info.com == Server.ALIVE.name:
                info: FuncAliveOutput = info
                self.events[msg.info.event_id].time = time()
                self.events[msg.info.event_id].n = info.event_n
                msg_r = self.parent.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=info.device_id,
                                                 func_input=FuncAliveInput())
                if self.parent.pyqtsignal_connected:
                    self.parent.signal.emit(msg.ext_to_int())
            elif info.com == PDUController.SET_PDU_STATE.name and not isinstance(self, SuperUserClientCmdLogic):
                # TODO: and not isinstance(self, SuperUserClientCmdLogic) IS STUPID
                power_settings: PowerSettings = self.parent.power_settings
                if power_settings.controller_id and power_settings.controller_id != 'manually':
                    result: FuncSetPDUStateOutput = info
                    self.parent.ctrl_status.power = bool(result.pdu.outputs[power_settings.output_id].state)
                    if hasattr(self.parent, 'activation'):
                        self.parent.activation()
        elif msg.com == MsgComExt.SHUTDOWN.msg_name:  # When one of devices shutdowns
            self.remove_device_from_connections(msg.sender_id)
            self.parent.send_status_pyqt()
        self.msg_out(msg_r)


class GeneralNonServerCmdLogic(GeneralCmdLogic):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.reacting_heartbeat = False

    def react_denied(self, msg: MessageExt):
        pass

    def react_directed(self, msg: MessageExt):
        super().react_directed(msg)

        if msg.com == MsgComExt.WELCOME_INFO_SERVER.msg_name:
            self.react_first_welcome(msg)

    def react_external(self, msg: MessageExt):
        super().react_external(msg)
        if msg.com == MsgComExt.HEARTBEAT_FULL.msg_name and not self.connections:
            self.react_heartbeat_full(msg)

    def react_forward(self, msg: MessageExt):
        pass

    def react_first_welcome(self, msg: MessageExt):
        msg_r = None
        try:
            messenger = self.parent.messenger
            info: WelcomeInfoServer = msg.info
            # Decrypt public_key of device crypted on device side with public key of Server
            info.session_key = messenger.decrypt_with_private(info.session_key)
            info.certificate = messenger.decrypt_with_private(info.certificate)
            server_connection = self.connections[msg.sender_id]
            certificates_db = self.parent.messenger.get_certificate(info.device_id)
            version = info.version
            if version != self.parent.version:
                raise DeviceError(f'Server version {version} does not correspond version of '
                                  f'device {self.parent.version}')
            if info.certificate in certificates_db:
                server_connection.session_key = info.session_key
                server_connection.access_level = AccessLevel.FULL
                server_connection.permission = Permission.GRANTED
                self.parent.send_status_pyqt()
                info_msg(self, 'INFO', f'Handshake with Server is accomplished. Session_key is obtained.')
            # power the Service controller
                if hasattr(self.parent, 'power'):
                    self.parent.power(func_input=FuncPowerInput(flag=True))
                    if self.parent.ctrl_status.power:
                        self.parent.activation()
            else:
                del self.connections[msg.sender_id]
                raise DeviceError("Server's certificate error")
        except (Exception, DeviceError) as e:
            msg_r = self.parent.generate_msg(msg_com=MsgComExt.ERROR, comments=f'{e}',
                                             receiver_id=msg.sender_id, reply_to=msg.id)
            error_logger(self, self.react_first_welcome, msg_r)
        self.msg_out(msg_r)

    def react_heartbeat_full(self, msg: MessageExt):
        param = {}
        for field_name in Connection.__annotations__:
            try:
                param[field_name] = getattr(msg.info, field_name)
            except AttributeError:
                pass

        info: HeartBeatFull = msg.info
        sockets = info.device_public_sockets
        info_msg(self, 'INFO', f'Info from Server is obtained for messenger operation.')
        from communication.messaging.messengers import FRONTEND_Server, BACKEND_Server
        self.parent.messenger.pause()
        if self.parent.type == DeviceType.CLIENT:
            addr = sockets[FRONTEND_Server]
        else:
            addr = sockets[BACKEND_Server]
        self.parent.messenger.add_dealer(addr, info.device_id)
        self.parent.messenger.unpause()


        from communication.logic.logic_functions import external_hb_logic
        self.register_event(name=msg.info.event_name, event_id=msg.info.event_id, logic_func=external_hb_logic,
                            original_owner=msg.info.device_id, tick=msg.info.event_tick, start_now=True)

        sleep(0.2)  # Give time to start event

        self.connections[DeviceId(info.device_id)] = Connection(**param)
        event = self.events['heartbeat']
        msg_welcome = self.parent.generate_msg(msg_com=MsgComExt.WELCOME_INFO_DEVICE,
                                               receiver_id=info.device_id, event=event)
        self.msg_out(msg_welcome)

    def react_internal(self, event: ThinkerEvent):
        if 'heartbeat' in event.name:
            if event.counter_timeout > self.timeout:
                if self.parent.messenger.attempts_to_restart_sub > 0:
                    self.parent.messenger.attempts_to_restart_sub -= 1
                    info_msg(self, 'INFO', f'Server is away...trying to restart sub socket. '
                                           f'Attempts left {self.parent.messenger.attempts_to_restart_sub}.')
                    info_msg(self, 'INFO', 'Setting event.counter_timeout to 0')
                    event.counter_timeout = 0
                    addr = self.connections[event.original_owner].device_public_sockets[PUB_Socket_Server]
                    self.parent.messenger.restart_socket(SUB_Socket, addr)
                else:
                    if not self.parent.messenger.are_you_alive_send:
                        info_msg(self, 'INFO', 'restart of sub socket did work, switching to demand pathway')
                        event.counter_timeout = 0
                        msg_i = self.parent.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=event.original_owner,
                                                         func_input=FuncAliveInput())
                        self.parent.messenger.are_you_alive_send = True
                        self.msg_out(msg_i)
                    else:
                        info_msg(self, 'INFO', f'{event.name} timeout is reached. Deleting the event {event.id}.')
                        info_msg(self, 'INFO', 'Server was away for too long...deleting service_info about Server')
                        self.remove_device_from_connections(event.original_owner)
                        self.parent.send_status_pyqt()


class ServerCmdLogic(GeneralCmdLogic):
    """
    Knows how to react to commands that SERVER messenger receives
    TODO:  BUG: several instances of the same devices can be started, and server will think that they are different
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def react_denied(self, msg: MessageExt):
        pass

    def react_external(self, msg: MessageExt):
        if msg.sender_id not in self.connections and msg.receiver_id == self.parent.device_id:
            self.react_first_welcome(msg)
        elif msg.forward_to:
            self.react_forward(msg)

        super().react_external(msg)

    def react_first_welcome(self, msg: MessageExt):
        msg_r = None
        try:
            messenger = self.parent.messenger
            info: WelcomeInfoDevice = msg.info
            # Decrypt public_key of device crypted on device side with public key of Server
            info.device_public_key = messenger.decrypt_with_private(info.device_public_key)
            info.certificate = messenger.decrypt_with_private(info.certificate)
            connections = self.connections
            certificate_db = self.parent.messenger.get_certificate(info.device_id)
            version = info.version
            if version != self.parent.version:
                raise DeviceError(f'Server version {version} does not correspond version of '
                                  f'device {self.parent.version}')
            if certificate_db == info.certificate:
                param = {}
                for field_name in info.__annotations__:
                    param[field_name] = getattr(info, field_name)
                # TODO: Actually check AccessLevel and Permission using password checksum
                param['access_level'] = AccessLevel.FULL
                param['permission'] = Permission.GRANTED
                connections[info.device_id] = Connection(**param)
                connections[info.device_id].device_type = DeviceType(connections[info.device_id].device_type)

                if PUB_Socket in info.device_public_sockets:
                    from communication.logic.logic_functions import external_hb_logic
                    messenger.subscribe_sub(address=info.device_public_sockets[PUB_Socket])
                    self.register_event(name=f'heartbeat:{info.device_name}:{info.device_id[-10:]}',
                                        logic_func=external_hb_logic,
                                        event_id=f'heartbeat:{info.device_id}',
                                        original_owner=info.device_id,
                                        start_now=True)
                session_key = messenger.gen_symmetric_key(info.device_id)
                self.connections[info.device_id].session_key = session_key
                msg_r = self.parent.generate_msg(msg_com=MsgComExt.WELCOME_INFO_SERVER, reply_to=msg.id,
                                                 receiver_id=msg.sender_id)
                self.parent.send_status_pyqt()
            else:
                del self.connections[msg.sender_id]
                raise DeviceError("Devices's certificate error")
        except (DeviceError, Exception) as e:
            msg_r = self.parent.generate_msg(msg_com=MsgComExt.ERROR, comments=f'{e}',
                                             receiver_id=msg.sender_id, reply_to=msg.id)
            error_logger(self, self.react_first_welcome, msg_r)
        finally:
            self.msg_out(msg_r)

    def react_forward(self, msg: MessageExt):
        if msg.forward_to in self.connections:
            msg_r = msg.copy(sender_id=self.parent.device_id, receiver_id=msg.forward_to, forward_to='',
                             forwarded_from=msg.sender_id, id=msg.id)
        else:
            msg_r = [self.parent.generate_msg(msg_com=MsgComExt.ERROR,
                                              comments=f'service {msg.forward_to} is not available',
                                              receiver_id=msg.sender_id, reply_to=msg.id)]
        self.msg_out(msg_r)

    def react_internal(self, event: ThinkerEvent):
        if 'heartbeat' in event.name:
            if event.counter_timeout > self.timeout:
                info_msg(self, 'INFO', f'Service {event.original_owner} was away for too long. Deleting it.')
                self.remove_device_from_connections(event.original_owner)
                self.parent.send_status_pyqt()


class SuperUserClientCmdLogic(GeneralNonServerCmdLogic):

    def react_broadcast(self, msg: MessageExt):
        def process_servers(self, msg):
            t = time()
            self.parent.active_servers[msg.sender_id] = t
            keys = []
            for key, value in self.parent.active_servers.items():
                if (t - value) > 3:
                    keys.append(key)
            if keys:
                for key in keys:
                    del self.parent.active_servers[key]

        super().react_broadcast(msg)
        process_servers(self, msg)

    def react_external(self, msg: MessageExt):
        super().react_external(msg)
        if msg.com == MsgComExt.DONE_IT.msg_name:
            info: Union[DoneIt, MsgError] = msg.info
            if info.com == Server.GET_AVAILABLE_SERVICES.name:
                self.parent.running_services[info.device_id] = info.device_available_services

    def react_first_welcome(self, msg: MessageExt):
        super().react_first_welcome(msg)
        client = self.parent
        for device_id in self.connections.keys():
            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=device_id,
                                      func_input=FuncAvailableServicesInput())
            self.msg_out(msg)


class ServiceCmdLogic(GeneralNonServerCmdLogic):
    pass


class CameraCtrlServiceCmdLogic(ServiceCmdLogic):
    pass


class DAQmxCtrlServiceCmdLogic(ServiceCmdLogic):
    pass


class StpMtrCtrlServiceCmdLogic(ServiceCmdLogic):
    pass


class PDUCtrlServiceCmdLogic(ServiceCmdLogic):
    pass


class ProjectManagerServiceCmdLogic(ServiceCmdLogic):
    pass
