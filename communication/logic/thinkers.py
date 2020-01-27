import logging
from time import time

import utilities.data.messages as mes
from communication.messaging.message_utils import MsgGenerator
from utilities.data.datastructures.mes_dependent import Connection
from utilities.data.messages import Message, DeviceInfoMes
from utilities.myfunc import info_msg, error_logger

module_logger = logging.getLogger(__name__)

from communication.logic import Thinker, ThinkerEvent


class GeneralCmdLogic(Thinker):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from communication.logic.logic_functions import internal_hb_logic
        self.register_event('heartbeat',
                            internal_hb_logic,
                            external_name=f'heartbeat:{self.parent.name}',
                            event_id=f'heartbeat:{self.parent.id}')

    def react_info(self, msg: Message):
        data = msg.data
        if data.com == MsgGenerator.HEARTBEAT.mes_name:
            if self.parent.pyqtsignal_connected:
                self.parent.signal.emit(msg)
            if data.info.device_id not in self.parent.connections:
                self.logger.info(msg)
                from communication.logic.logic_functions import external_hb_logic
                self.register_event(name=data.info.event_name,
                                    event_id=data.info.event_id,
                                    logic_func=external_hb_logic,
                                    original_owner=data.info.device_id,
                                    start_now=True)
                self.parent.connections[data.info.device_id] = Connection(DeviceInfoMes(device_id=data.info.device_id,
                                                                                        messenger_id=msg.body.sender_id))
                msg = MsgGenerator.hello(device=self.parent)
                self.add_task_out(msg)
            else:
                # TODO: potential danger of calling non-existing event
                self.events[data.info.event_id].time = time()
                self.events[data.info.event_id].n = data.info.n

    def react_unknown(self, msg: Message):
        # TODO: correct
        self.logger.info('Fuck Yeah')

    def react_reply(self, msg: Message):
        data = msg.data
        info_msg(self, 'REPLY_IN', extra=str(msg.short()))

        if msg.reply_to in self.demands_pending_answer:
            del self.demands_pending_answer[msg.reply_to]
            self.logger.info(f'react_reply: Msg {msg.reply_to} reply is obtained')

        if data.com == MsgGenerator.WELCOME_INFO.mes_name:
            if data.info.device_id in self.parent.connections:
                self.logger.info(f'Server {data.info.device_id} is active. Handshake was undertaken')
                connection: Connection = self.parent.connections[data.info.device_id]
                connection.device_info = data.info
                session_key = self.parent.messenger.decrypt_with_private(data.info.session_key)
                self.parent.messenger.fernet = self.parent.messenger.create_fernet(session_key)

    def react_demand(self, msg: Message):
        info_msg(self, 'REQUEST', extra=str(msg.short()))

    def react_internal(self, event: ThinkerEvent):
        if 'server_heartbeat' in event.name:
            if event.counter_timeout > 10:
                self.logger.info('Server was away for too long...deleting info about Server')
                del self.parent.connections[event.original_owner]
                self.unregister_event(event.id)
        else:
            self.logger.info('react_internal: I do not know what to do')


class ServerCmdLogic(Thinker):
    """
    Knows how to react to commands that SERVER messenger receives
    TODO:  BUG: several instances of the same devices can be started, and server will think that they are different
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from communication.logic.logic_functions import internal_hb_logic
        self.register_event(name='heartbeat',
                            external_name='server_heartbeat',
                            logic_func=internal_hb_logic)
        self._forward_binding = {}

    def react_info(self, msg: Message):
        data = msg.data
        print(msg)
        # TODO: if section should be added to check weather device which send cmd is in connections or not
        # at this moment connections is dict with key = device_id
        if msg.body.sender_id in self.parent.connections:
            if MsgGenerator.HEARTBEAT.mes_name in data.com:
                try:
                    self.events[data.info.event_id].time = time()
                    self.events[data.info.event_id].n = data.info.n
                except KeyError as e:
                    self.logger.error(e)
            elif data.com == 'shutdown':
                # TODO: the info is not deleted from _frontend sockets or backend sockets
                self.remove_device_from_connections(data.info.device_id)
                self.parent.send_status_pyqt(com='status_server_info_full')

    def react_demand(self, msg: Message):
        data = msg.data
        cmd = data.com
        info_msg(self, 'REQUEST', extra=str(msg.short()))
        reply = True

        if msg.body.receiver_id != self.parent.id:
            if msg.body.receiver_id in self.parent.connections:
                msg_i = MsgGenerator.forward_msg(device=self.parent,
                                                 msg_i=msg)
            else:
                msg_i = [MsgGenerator.available_services_reply(device=self.parent, msg_i=msg),
                         MsgGenerator.error(device=self.parent,
                                            comments=f'service {data.info.service_id} is not available anymore',
                                            msg_i=msg)]

        else:
            if cmd == MsgGenerator.HELLO.mes_name:
                try:
                    device_info: DeviceInfoMes = data.info
                    connections = self.parent.connections
                    if data.info.type not in ('service', 'client'):
                        raise Exception(f'{self}:{device_info.type} is not known')

                    if device_info.device_id not in connections:
                        connections[device_info.device_id] = Connection(device_info=data.info)
                        if 'publisher' in device_info.public_sockets:
                            from communication.logic.logic_functions import external_hb_logic
                            self.parent.messenger.subscribe_sub(address=device_info.public_sockets['publisher'])
                            a = f'heartbeat:{data.info.name}'
                            self.register_event(name=f'heartbeat:{data.info.name}',
                                                logic_func=external_hb_logic,
                                                event_id=f'heartbeat:{data.info.device_id}',
                                                original_owner=device_info.device_id,
                                                start_now=True)
                        session_key = self.parent.messenger.gen_symmetric_key(device_info.device_id)
                        session_key_encrypted = self.parent.messenger.encrypt_with_public(session_key,
                                                                                          device_info.public_key)
                        msg_i = MsgGenerator.welcome_info(device=self.parent, msg_i=msg,
                                                          session_key=session_key_encrypted)
                        self.parent.send_status_pyqt(com='status_server_info_full')
                    else:
                        msg_i = MsgGenerator.welcome_info(device=self.parent, msg_i=msg)
                except Exception as e:
                    self.logger.error(e)
                    msg_i = MsgGenerator.error(device=self.parent, comments=repr(e), msg_i=msg)
            elif cmd == MsgGenerator.AVAILABLE_SERVICES_DEMAND.mes_name:
                msg_i = MsgGenerator.available_services_reply(device=self.parent, msg_i=msg)
            elif cmd == MsgGenerator.POWER_ON_DEMAND.mes_name:
                # TODO: service must be realized instead
                # Server here always replied the same way to all services
                comments = """"I always say, that power is ON, I hope the user have turned on power already"""
                msg_i = MsgGenerator.power_on_reply(self.parent, msg_i=msg, flag=True, comments=comments)
            else:
                msg_i = MsgGenerator.error(device=self.parent, msg_i=msg,
                                           comments=f'Unknown Message com: {msg.data.com}')
        self.msg_out(reply, msg_i)

    def react_reply(self,  msg: Message):
        data = msg.data
        cmd = data.com
        info_msg(self, 'REPLY_IN', extra=str(msg.short()))
        reply = False

        if msg.body.receiver_id != self.parent.id:
            msg_i = MsgGenerator.forward_msg(device=self.parent,
                                             msg_i=msg)
            if msg.reply_to in self.demands_pending_answer:
                del self.demands_pending_answer[msg.reply_to]
                self.logger.info(f'react_reply: Msg: {msg.reply_to} reply is obtained and forwarded to intial demander')
            reply = True

        else:
            pass
        self.msg_out(reply, msg_i)

    def react_unknown(self, msg: Message):
        msg_i = MsgGenerator.error(self.messenger, msg_i=msg, comments=f'unknown message com: {msg.data.com}')
        info_msg(self, 'REPLY', extra=repr(msg_i))
        self.messenger.add_task_out(self.msg_i)

    def react_internal(self, event: ThinkerEvent):
        if 'heartbeat' in event.name:
            if event.counter_timeout > 5:
                try:
                    connections = self.parent.connections
                    self.logger.info(f"""{connections[event.original_owner].device_info.type} {event.name} 
                                     was away for too long...removing it from active services, deleting its tasks""")
                    self.unregister_event(event.id)
                    del connections[event.original_owner]
                    # TODO: tasks should be deleted here
                except KeyError as e:
                    error_logger(self, self.react_internal, e)
                    self.unregister_event(event.id)
                self.parent.send_status_pyqt(com='status_server_info_full')
        else:
            self.logger.info(f'react_internal: I do not know what to do, {event.name} is not known')


class SuperUserClientCmdLogic(GeneralCmdLogic):

    def react_info(self, msg: Message):
        super().react_info(msg)

    def react_internal(self, event: ThinkerEvent):
        super().react_internal(event)

    def react_unknown(self, msg: Message):
        super().react_unknown(msg)

    def react_reply(self, msg: Message):
        super().react_reply(msg)
        data = msg.data
        if self.parent.pyqtsignal_connected:
            self.parent.signal.emit(msg)
        if data.com == MsgGenerator.WELCOME_INFO.mes_name:
            msg = MsgGenerator.available_services_demand(device=self.parent)
            self.add_task_out(msg)


class ServiceCmdLogic(GeneralCmdLogic):

    def react_reply(self, msg: Message):
        super().react_reply(msg)
        data = msg.data
        if data.com == MsgGenerator.POWER_ON_REPLY.mes_name:
            self.parent.device_status.power = data.info.power_on
            self.logger.info(data.info.comments)


class StpMtrCtrlServiceCmdLogic(ServiceCmdLogic):

    def react_demand(self, msg: Message):
        super().react_demand(msg)
        data = msg.data
        reply = False
        msg_i = []
        if data.com == MsgGenerator.INFO_SERVICE_DEMAND.mes_name:
            msg_i = MsgGenerator.info_service_reply(device=self.parent, msg_i=msg)
            reply = True
        elif data.com == MsgGenerator.DO_IT.mes_name:
            reply = False
            if not self.parent.add_to_executor(self.parent.execute_com, msg=msg):
                self.logger.error(f'Adding to executor {msg.data.info} failed')
        self.msg_out(reply, msg_i)
