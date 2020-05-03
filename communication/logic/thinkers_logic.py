import logging
from time import time

from pip._internal import self_outdated_check

from communication.logic.thinker import Thinker, ThinkerEvent
from communication.messaging.messages import *
from communication.messaging.messengers import PUB_Socket, SUB_Socket, PUB_Socket_Server
from datastructures.mes_independent.devices_dataclass import Connection
from utilities.myfunc import info_msg, error_logger

module_logger = logging.getLogger(__name__)


class GeneralCmdLogic(Thinker):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from communication.logic.logic_functions import internal_hb_logic
        self.register_event('heartbeat', internal_hb_logic, external_name=f'heartbeat:{self.parent.name}',
                            event_id=f'heartbeat:{self.parent.id}')
        self.timeout = int(self.parent.get_general_settings()['timeout'])

    def react_broadcast(self, msg: MessageExt):
        if msg.com == MsgComExt.HEARTBEAT.msg_name:
            try:
                self.events[msg.sender_id].time = time()
                self.events[msg.sender_id].n = msg.info.n
            except KeyError as e:
                error_logger(self, self.react_broadcast, e)
        elif msg.com == MsgComExt.SHUTDOWN.msg_name:  # When one of devices connected to server shutdowns
            self.remove_device_from_connections(msg.sender_id)
            self.parent.send_status_pyqt()

    def react_forward(self, msg: MessageExt):
        pass

    def react_first_welcome(self, msg: MessageExt):
        pass

    def react_directed(self, msg: MessageExt):
        if self.parent.pyqtsignal_connected:
            # Convert MessageExt to MessageInt and emit it
            self.parent.signal.emit(msg.ext_to_int())

        msg_r = None
        if msg.com == MsgComExt.ALIVE.msg_name:
            if msg.body.sender_id in self.parent.connections:
                msg_r = None  # MsgGenerator.are_you_alive_reply(device=self.parent, msg_i=msg)
        elif msg.com == MsgComExt.DO_IT.mes_name:
            if not self.parent.add_to_executor(self.parent.execute_com, msg=msg):
                self.logger.error(f'Adding to executor {msg.info} failed')

        self.msg_out(msg_r)

        if msg.info.device_id not in self.parent.connections:
            self.logger.info(msg.short())
            from communication.logic.logic_functions import external_hb_logic
            self.register_event(name=msg.info.event_name,
                                event_id=msg.info.event_id,
                                logic_func=external_hb_logic,
                                original_owner=msg.info.device_id,
                                start_now=True)
            self.parent.connections[msg.info.device_id] = Connection(WelcomeInfoDevice(device_id=msg.info.device_id,
                                                                                       messenger_id=msg.sender_id))
            msg_i = MsgGenerator.hello(device=self.parent)
            self.msg_out(True, msg_i)
        else:
            # TODO: potential danger of calling non-existing event
            self.events[msg.info.event_id].time = time()
            self.events[msg.info.event_id].n = msg.info.n

    def react_first_welcome(self, msg: MessageExt):
        msg_r = None
        if msg.com == MsgComExt.WELCOME_INFO_SERVER.msg_name:
            try:
                messenger = self.parent.messenger
                info: WelcomeInfoServer = msg.info
                # Decrypt public_key of device crypted on device side with public key of Server
                info.session_key = messenger.decrypt_with_private(info.device_public_key)
                connections = self.parent.connections
                param = {}
                for field_name in info.__annotations__:
                    param[field_name] = getattr(info, field_name)
                # TODO: Actually check AccessLevel and ConnectionPermission using password checksum
                param['AccessLevel'] = AccessLevel.FULL
                param['ConnectionPermission'] = ConnectionPermission.GRANTED
                connections[info.device_id] = Connection(**param)
                if PUB_Socket_Server in info.device_public_sockets:
                    from communication.logic.logic_functions import external_hb_logic
                    messenger.subscribe_sub(address=info.device_public_sockets[PUB_Socket_Server])
                    self.register_event(name=f'heartbeat:{info.device_name}',
                                        logic_func=external_hb_logic,
                                        event_id=f'heartbeat:{info.device_id}',
                                        original_owner=info.device_id,
                                        start_now=True)
                self.parent.send_status_pyqt()
            except Exception as e:  # TODO: change Exception to something reasonable
                msg_r = self.parent.generate_msg(msg_com=MsgComExt.ERROR, comments=f'{e}',
                                                 receiver_id=msg.sender_id, reply_to=msg.id)
        self.msg_out(msg_r)

    def react_external(self, msg: MessageExt):
        # TODO: add decision on permission
        # HEARTBEATS and SHUTDOWNS...maybe something else later
        if msg.receiver_id == '' and msg.sender_id in self.parent.connections:
            self.react_broadcast(msg)
        # Forwarding message or sending [MsgComExt.AVAILABLE_SERVICES, MsgComExt.ERROR] back
        elif msg.receiver_id != self.parent.id and msg.receiver_id != '':
            self.react_forward(msg)
        # WELCOME INFO from another device or Directed message for the first time
        elif msg.sender_id not in self.parent.connections and msg.receiver_id == self.parent.id:
            self.react_first_welcome(msg)
        # When the message is dedicated to Device
        elif msg.sender_id in self.parent.connections and msg.receiver_id == self.parent.id:
            self.react_directed(msg)
        else:
            pass  # TODO: that I do not know what it is...add MsgError

    def react_internal(self, event: ThinkerEvent):
        if 'server_heartbeat' in event.name:
            if event.counter_timeout > self.timeout:
                if self.parent.messenger._attempts_to_restart_sub > 0:
                    info_msg(self, 'INFO', 'Server is away...trying to restart sub socket')
                    info_msg(self, 'INFO', 'Setting event.counter_timeout to 0')
                    self.parent.messenger._attempts_to_restart_sub -= 1
                    event.counter_timeout = 0
                    addr = self.parent.connections[event.original_owner].device_info.public_sockets[PUB_Socket]  # TODO: check if it is PUB_scoket or Server PUB_socket
                    self.parent.messenger.restart_socket('sub', addr)
                else:
                    if not self.parent.messenger._are_you_alive_send:
                        info_msg(self, 'INFO', 'restart of sub socket did work, switching to demand pathway')
                        event.counter_timeout = 0
                        msg_i = MsgGenerator.are_you_alive_demand(device=self.parent, context=f'EVENT:{event.id}')
                        self.parent.messenger._are_you_alive_send = True
                        self.msg_out(True, msg_i)
                    else:
                        info_msg(self, 'INFO', 'Server was away for too long...deleting info about Server')
                        del self.parent.connections[event.original_owner]


class ServerCmdLogic(GeneralCmdLogic):
    """
    Knows how to react to commands that SERVER messenger receives
    TODO:  BUG: several instances of the same devices can be started, and server will think that they are different
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from communication.logic.logic_functions import internal_hb_logic
        self.register_event(name='heartbeat', external_name='server_heartbeat', logic_func=internal_hb_logic)
        self.timeout = int(self.parent.get_general_settings()['timeout'])

    def react_denied(self, msg: MessageExt):
        pass

    def react_first_welcome(self, msg: MessageExt):
        msg_r = None
        if msg.com == MsgComExt.WELCOME_INFO_DEVICE.msg_name:
            try:
                messenger = self.parent.messenger
                info: WelcomeInfoDevice = msg.info
                # Decrypt public_key of device crypted on device side with public key of Server
                info.device_public_key = messenger.decrypt_with_private(info.device_public_key)
                connections = self.parent.connections
                param = {}
                for field_name in info.__annotations__:
                    param[field_name] = getattr(info, field_name)
                # TODO: Actually check AccessLevel and ConnectionPermission using password checksum
                param['AccessLevel'] = AccessLevel.FULL
                param['ConnectionPermission'] = ConnectionPermission.GRANTED
                connections[info.device_id] = Connection(**param)
                if PUB_Socket in info.device_public_sockets:
                    from communication.logic.logic_functions import external_hb_logic
                    messenger.subscribe_sub(address=info.device_public_sockets[PUB_Socket])
                    self.register_event(name=f'heartbeat:{info.device_name}',
                                        logic_func=external_hb_logic,
                                        event_id=f'heartbeat:{info.device_id}',
                                        original_owner=info.device_id,
                                        start_now=True)
                session_key = messenger.gen_symmetric_key(info.device_id)
                self.parent.connections[info.device_id].session_key = session_key
                msg_r = self.parent.generate_msg(msg_com=MsgComExt.WELCOME_INFO_SERVER, reply_to=msg.id,
                                                 receiver_id=msg.sender_id)
                self.parent.send_status_pyqt()
            except Exception as e:  # TODO: change Exception to something reasonable
                msg_r = self.parent.generate_msg(msg_com=MsgComExt.ERROR, comments=f'{e}',
                                                 receiver_id=msg.sender_id, reply_to=msg.id)
        self.msg_out(msg_r)

    def react_forward(self, msg: MsgComExt):
        msg_r = None
        if msg.receiver_id in self.parent.connections:
            info_msg(self, 'INFO', f'Msg id={msg.id}, com={msg.com} is forwarded to {msg.receiver_id}')
        else:
            msg_r = [self.parent.generate_msg(msg_com=MsgComExt.AVAILABLE_SERVICES, receiver_id=msg.sender_id,
                                              reply_to=msg.id),
                     self.parent.generate_msg(msg_com=MsgComExt.ERROR,
                                              comments=f'service {msg.receiver_id} is not available',
                                              receiver_id=msg.sender_id, reply_to=msg.id)]
        self.msg_out(msg_r)

    def react_internal(self, event: ThinkerEvent):
        if 'heartbeat' in event.name:
            if event.counter_timeout > self.timeout:
                self.logger.info('Service was away for too long...deleting info about service')
                self.remove_device_from_connections(event.original_owner)
                self.parent.send_status_pyqt()


class SuperUserClientCmdLogic(GeneralCmdLogic):
    pass


class ServiceCmdLogic(GeneralCmdLogic):

    def react_directed(self, msg: MessageExt):
        super().react_directed(msg)
        reply = False
        data = msg.data
        msg_i = []
        if data.com == MsgGenerator.INFO_SERVICE_DEMAND.mes_name:
            msg_i = MsgGenerator.info_service_reply(device=self.parent, msg_i=msg)
            reply = True
        elif data.com == MsgGenerator.DO_IT.mes_name:
            reply = False
            if not self.parent.add_to_executor(self.parent.execute_com, msg=msg):
                self.logger.error(f'Adding to executor {msg.data.info} failed')
        else:
            reply = True
            msg_i = MsgGenerator.error(device=self.parent, msg_i=msg, comments=f'Unknown Message com: {msg.data.com}')
        self.msg_out(reply, msg_i)

    # OLD reply
        data = msg.data
        if data.com == MsgGenerator.POWER_ON_REPLY.mes_name:
            self.parent.device_status.power = data.info.power_on
            self.logger.info(data.info.comments)


class StpMtrCtrlServiceCmdLogic(ServiceCmdLogic):
    pass


class ProjectManagerServiceCmdLogic(ServiceCmdLogic):
    pass
