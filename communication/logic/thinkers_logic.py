import logging
from time import time, sleep


from communication.logic.thinker import Thinker, ThinkerEvent
from communication.messaging.messages import *
from communication.messaging.messengers import PUB_Socket, SUB_Socket, PUB_Socket_Server
from datastructures.mes_independent.devices_dataclass import Connection
from utilities.myfunc import info_msg, error_logger

module_logger = logging.getLogger(__name__)


class GeneralCmdLogic(Thinker):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from communication.logic.logic_functions import internal_hb_logic, external_hb_logic
        self.register_event('heartbeat', internal_hb_logic, external_name=f'heartbeat:{self.parent.name}',
                            event_id=f'heartbeat:{self.parent.id}')
        self.timeout = int(self.parent.get_general_settings()['timeout'])
        self.connections = self.parent.connections

    def react_broadcast(self, msg: MessageExt):
        if msg.com == MsgComExt.HEARTBEAT.msg_name:
            try:
                self.events[msg.info.event_id].time = time()
                self.events[msg.info.event_id].n = msg.info.event_n
                if self.parent.pyqtsignal_connected:
                    self.parent.signal.emit(msg.ext_to_int())
            except (KeyError, TypeError) as e:
                error_logger(self, self.react_broadcast, e)
        elif msg.com == MsgComExt.SHUTDOWN.msg_name:  # When one of devices shutdowns
            self.remove_device_from_connections(msg.sender_id)
            self.parent.send_status_pyqt()

    def react_directed(self, msg: MessageExt):
        if self.parent.pyqtsignal_connected:
            # Convert MessageExt to MessageInt and emit it
            msg_int = msg.ext_to_int()
            self.parent.signal.emit(msg_int)
        msg_r = None
        if msg.com == MsgComExt.ALIVE.msg_name:
            if msg.sender_id in self.parent.connections:
                msg_r = None  # MsgGenerator.are_you_alive_reply(device=self.parent_logger, msg_i=msg)
        elif msg.com == MsgComExt.DO_IT.msg_name:
            if not self.parent.add_to_executor(self.parent.execute_com, msg=msg):
                self.logger.error(f'Adding to executor {msg.info} failed')
        elif msg.com == MsgComExt.DONE_IT.msg_name:
            if msg.reply_to in self.forwarded_messages:
                initial_msg: MessageExt = self.forwarded_messages[msg.reply_to]
                msg_r = msg.copy(receiver_id=initial_msg.sender_id, reply_to=initial_msg.id,
                                 sender_id=self.parent.id)
                del self.forwarded_messages[msg.reply_to]
                info_msg(self, 'INFO', f'Msg {initial_msg.id} com {initial_msg.com} is deleted from forwarded messages')
            else:
                pass  # TODO: at this moment Server does not do DO_IT command for itself, it only forwards
        elif msg.com == MsgComExt.WELCOME_INFO_SERVER.msg_name:
            self.react_first_welcome(msg)

        self.msg_out(msg_r)

    def react_external(self, msg: MessageExt):
        # TODO: add decision on permission
        # HEARTBEATS and SHUTDOWNS...maybe something else later
        if msg.receiver_id == '' and msg.sender_id in self.connections:
            self.react_broadcast(msg)
        # Only works for non-Server devices, since only Server emits MsgComExt.HEARTBEAT_FULL
        elif msg.com == MsgComExt.HEARTBEAT_FULL.msg_name and msg.sender_id not in self.connections:
            self.react_heartbeat_full(msg)
        # Forwarding message. Applicable only for SERVER
        elif msg.receiver_id != self.parent.id and msg.receiver_id != '':
            self.react_forward(msg)
        # When the message is dedicated to Device
        elif msg.sender_id in self.connections and msg.receiver_id == self.parent.id:
            self.react_directed(msg)
        # For Server
        elif msg.sender_id not in self.connections and msg.receiver_id == self.parent.id:
            self.react_first_welcome(msg)
        else:
            pass  # TODO: that I do not know what it is...add MsgError

    def react_forward(self, msg: MessageExt):
        pass

    def react_first_welcome(self, msg: MessageExt):
        msg_r = None
        try:
            messenger = self.parent.messenger
            info: WelcomeInfoServer = msg.info
            # Decrypt public_key of device crypted on device side with public key of Server
            info.session_key = messenger.decrypt_with_private(info.session_key)
            server_connection = self.connections[msg.sender_id]
            # TODO: Actually check AccessLevel and Permission using password checksum
            server_connection.session_key = info.session_key
            server_connection.access_level = AccessLevel.FULL
            server_connection.permission = Permission.GRANTED
            self.parent.send_status_pyqt()
            info_msg(self, 'INFO', f'Handshake with Server is accomplished. Session_key is obtained.')
        except Exception as e:  # TODO: change Exception to something reasonable
            msg_r = self.parent.generate_msg(msg_com=MsgComExt.ERROR, comments=f'{e}',
                                             receiver_id=msg.sender_id, reply_to=msg.id)
        self.msg_out(msg_r)

    def react_heartbeat_full(self, msg: MessageExt):
        param = {}
        for field_name in Connection.__annotations__:
            try:
                param[field_name] = getattr(msg.info, field_name)
            except AttributeError:
                pass

        from communication.logic.logic_functions import external_hb_logic
        self.register_event(name=msg.info.event_name, event_id=msg.info.event_id, logic_func=external_hb_logic,
                            original_owner=msg.info.device_id, tick=msg.info.event_tick, start_now=True)

        sleep(0.2)  # Give time to start event

        self.parent.server_id = msg.info.device_id
        self.parent.connections[DeviceId(msg.info.device_id)] = Connection(**param)
        event = self.events['heartbeat']
        msg_welcome = self.parent.generate_msg(msg_com=MsgComExt.WELCOME_INFO_DEVICE,
                                               receiver_id=msg.info.device_id, event=event)
        self.msg_out(msg_welcome)

    def react_internal(self, event: ThinkerEvent):
        if 'heartbeat' in event.name:
            if event.counter_timeout > self.timeout:
                self.logger.info(f'{event.name} timeout is reached. Deleting the event {event.id}.')
                self.remove_device_from_connections(event.original_owner)
                self.parent.send_status_pyqt()
                # if self.parent_logger.messenger._attempts_to_restart_sub > 0:
                #     info_msg(self, 'INFO', 'Server is away...trying to restart sub socket')
                #     info_msg(self, 'INFO', 'Setting event.counter_timeout to 0')
                #     self.parent_logger.messenger._attempts_to_restart_sub -= 1
                #     event.counter_timeout = 0
                #     addr = self.parent_logger.connections[event.original_owner].device_info.public_sockets[PUB_Socket_Server]
                #     self.parent_logger.messenger.restart_socket(SUB_Socket, addr)
                # else:
                #     if not self.parent_logger.messenger._are_you_alive_send:
                #         info_msg(self, 'INFO', 'restart of sub socket did work, switching to demand pathway')
                #         event.counter_timeout = 0
                #         msg_i = self.parent_logger.generate_msg(msg_com=MsgComExt.ALIVE, receiver_id=event.original_owner)
                #         self.parent_logger.messenger._are_you_alive_send = True
                #         self.msg_out(True, msg_i)
                #     else:
                #         info_msg(self, 'INFO', 'Server was away for too long...deleting service_info about Server')
                #         del self.parent_logger.connections[event.original_owner]


class ServerCmdLogic(GeneralCmdLogic):
    """
    Knows how to react to commands that SERVER messenger receives
    TODO:  BUG: several instances of the same devices can be started, and server will think that they are different
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from communication.logic.logic_functions import internal_hb_logic

    def react_denied(self, msg: MessageExt):
        pass

    def react_first_welcome(self, msg: MessageExt):
        msg_r = None
        try:
            messenger = self.parent.messenger
            info: WelcomeInfoDevice = msg.info
            # Decrypt public_key of device crypted on device side with public key of Server
            info.device_public_key = messenger.decrypt_with_private(info.device_public_key)
            connections = self.parent.connections
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

    def react_forward(self, msg: MessageExt):
        if msg.receiver_id in self.parent.connections:
            info_msg(self, 'INFO', f'Msg id={msg.id}, com={msg.com} is forwarded to {msg.receiver_id}')
            msg_r = msg.copy(sender_id=self.parent.id)
            self.add_to_forwarded(msg_forwarded=msg_r, msg_arrived=msg)
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
                info_msg(self, 'INFO', 'Service was away for too long...deleting info about service')
                self.remove_device_from_connections(event.original_owner)
                self.parent.send_status_pyqt()


class SuperUserClientCmdLogic(GeneralCmdLogic):
    pass


class ServiceCmdLogic(GeneralCmdLogic):
    pass


class StpMtrCtrlServiceCmdLogic(ServiceCmdLogic):
    pass


class ProjectManagerServiceCmdLogic(ServiceCmdLogic):
    pass
