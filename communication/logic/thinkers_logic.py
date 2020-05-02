import logging
from time import time

from communication.logic.thinker import Thinker, ThinkerEvent
from communication.messaging.messages import *
from datastructures.mes_independent.devices_dataclass import Connection
from utilities.myfunc import info_msg, error_logger

module_logger = logging.getLogger(__name__)


class GeneralCmdLogic(Thinker):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from communication.logic.logic_functions import internal_hb_logic
        self.register_event('heartbeat',  internal_hb_logic, external_name=f'heartbeat:{self.parent.name}',
                            event_id=f'heartbeat:{self.parent.id}')
        self.timeout = int(self.parent.get_general_settings()['timeout'])

    def react_directed(self, msg: MessageExt):
        if self.parent.pyqtsignal_connected:
            # Convert MessageExt to MessageInt and emit it
            self.parent.signal.emit(msg.ext_to_int())

        reply = False
        msg_i = []
        if msg.com == MsgGenerator.ARE_YOU_ALIVE_DEMAND.mes_name:
            if msg.body.sender_id in self.parent.connections:
                msg_i = MsgGenerator.are_you_alive_reply(device=self.parent, msg_i=msg)
            else:
                msg_i = MsgGenerator.error(device=self.parent,
                                       comments=f'service/client {msg.body.sender_id} is not known to server',
                                       msg_i=msg)
            reply = True

        self.msg_out(reply, msg_i)

        if msg.com == MsgComExt.HEARTBEAT.name:
            if self.parent.pyqtsignal_connected:
                self.parent.signal.emit(msg)
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

        info_msg(self, 'REPLY_IN', extra=str(msg.short()))

        if msg.com == MsgComExt.WELCOME_INFO.mes_name:
            if msg.info.device_id in self.parent.connections:
                self.logger.info(f'Server {msg.info.device_id} is active. Handshake was undertaken')
                connection: Connection = self.parent.connections[msg.info.device_id]
                connection.device_info = msg.info
                session_key = self.parent.messenger.decrypt_with_private(msg.info.session_key)
                # TODO: replace with setter
                self.parent.messenger.fernet = self.parent.messenger.create_fernet(session_key)
        elif msg.com == MsgGenerator.ARE_YOU_ALIVE_REPLY.mes_name:
            self.events['server_heartbeat'].time = time()
            self.parent.messenger._are_you_alive_send = False

    def react_internal(self, event: ThinkerEvent):
        if 'server_heartbeat' in event.name:
            if event.counter_timeout > self.timeout:
                if self.parent.messenger._attempts_to_restart_sub > 0:
                    info_msg(self, 'INFO', 'Server is away...trying to restart sub socket')
                    info_msg(self, 'INFO', 'Setting event.counter_timeout to 0')
                    self.parent.messenger._attempts_to_restart_sub -= 1
                    event.counter_timeout = 0
                    addr = self.parent.connections[event.original_owner].device_info.public_sockets['publisher']
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
                        self.unregister_event(event.id)


class ServerCmdLogic(Thinker):
    """
    Knows how to react to commands that SERVER messenger receives
    TODO:  BUG: several instances of the same devices can be started, and server will think that they are different
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from communication.logic.logic_functions import internal_hb_logic
        self.register_event(name='heartbeat', external_name='server_heartbeat', logic_func=internal_hb_logic)
        self.timeout = int(self.parent.get_general_settings()['timeout'])

    def react_directed(self, msg: MessageExt):
        # Forwarding message or sending [MsgComExt.AVAILABLE_SERVICES, MsgComExt.ERROR] back
        if msg.receiver_id != self.parent.id and msg.receiver_id != '':
            if msg.receiver_id in self.parent.connections:
                msg_i = msg
                info_msg(self, 'INFO', f'Msg id={msg.id}, com={msg.com} is forwarded to {msg.receiver_id}')
            else:
                msg_i = [self.parent.generate_msg(msg_com=MsgComExt.AVAILABLE_SERVICES, receiver_id=msg.sender_id,
                                                  reply_to=msg.id),
                         self.parent.generate_msg(msg_com=MsgComExt.ERROR,
                                                  comments=f'service {msg.receiver_id} is not available',
                                                  receiver_id=msg.sender_id, reply_to=msg.id)]
        # HEARTBEATS...maybe something else later
        elif msg.receiver_id == '' and msg.sender_id in self.parent.connections:
            if msg.com == MsgComExt.HEARTBEAT.com_name:
                try:
                    self.events[msg.info.event_id].time = time()
                    self.events[msg.info.event_id].n = msg.info.n
                except KeyError as e:
                    error_logger(self, self.react_directed, e)
        # WELCOME INFO from another device
        elif msg.sender_id not in self.parent.connections and msg.receiver_id == self.parent.id:
            if msg.com == MsgComExt.WELCOME_INFO_DEVICE.msg_name:
                try:
                    device_info: WelcomeInfoDevice = msg.info
                    connections = self.parent.connections
                    if device_info.device_id not in connections:
                        connections[device_info.device_id] = Connection(device_info=device_info)
                        if 'publisher' in device_info.public_sockets:
                            from communication.logic.logic_functions import external_hb_logic
                            self.parent.messenger.subscribe_sub(address=device_info.public_sockets['publisher'])
                            self.register_event(name=f'heartbeat:{device_info.device_name}',
                                                logic_func=external_hb_logic,
                                                event_id=f'heartbeat:{device_info.device_id}',
                                                original_owner=device_info.device_id,
                                                start_now=True)
                        session_key = self.parent.messenger.gen_symmetric_key(device_info.device_id)
                        device_public_key = self.parent.messenger.decrypt_with_private(device_info.public_key)
                        session_key_encrypted = self.parent.messenger.encrypt_with_public(session_key,
                                                                                          device_public_key)
                        msg_i = self.parent.generate_msg(msg_com=MsgComExt.WELCOME_INFO_SERVER, reply_to=msg.id,
                                                         receiver_id=msg.sender_id)
                        self.parent.send_status_pyqt()
                except Exception as e:  # TODO: change Exception to something reasonable
                    pass  #  TODO: add functionality
        # When the message is dedicated to Server
        elif msg.sender_id in self.parent.connections and msg.receiver_id == self.parent.id:
            if msg.com == MsgComExt.ALIVE.msg_name:
                if msg.body.sender_id in self.parent.connections:
                    msg_i = None #MsgGenerator.are_you_alive_reply(device=self.parent, msg_i=msg)
            elif msg.com == MsgComExt.DO_IT.mes_name:
                reply = False
                if not self.parent.add_to_executor(self.parent.execute_com, msg=msg):
                    self.logger.error(f'Adding to executor {msg.info} failed')
            elif msg.com == MsgComExt.SHUTDOWN.msg_name:  # When one of devices connected to server shutdowns
                self.remove_device_from_connections(msg.info.device_id)
                self.parent.send_status_pyqt()
        else:
            pass  # TODO: that I do not know what it is...add MsgError

        self.msg_out(reply, msg_i)

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
