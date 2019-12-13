import logging
from threading import Timer
from time import time

from communication.messaging.message_utils import gen_msg
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
        if data.com == 'heartbeat':
            if self.parent.pyqtsignal_connected:
                self.parent.signal.emit(msg)
            if data.info.event_id not in self.events.keys():
                self.logger.info(msg)
                from communication.logic.logic_functions import external_hb_logic
                self.register_event(name=data.info.event_name,
                                    event_id=data.info.event_id,
                                    logic_func=external_hb_logic,
                                    original_owner=data.info.device_id,
                                    start_now=True)
                self.parent.connections[data.info.device_id] = Connection(heartbeat_info=data.info)
                msg = gen_msg('hello', device=self.parent)
                self.add_task_out(msg)
            else:
                self.events[data.info.event_id].time = time()
                self.events[data.info.event_id].n = data.info.n

    def react_internal(self, event: ThinkerEvent):
        if 'server_heartbeat' in event.name:
            if event.counter_timeout > 5:
                self.logger.info('Server was away for too long...deleting info about Server')
                del self.parent.connections[event.original_owner]
                self.unregister_event(event.id)
        else:
            self.logger.info('react_internal: I do not know what to do')

    def react_unknown(self, msg: Message):
        # TODO: correct
        self.logger.info('Fuck Yeah')

    def react_reply(self, msg: Message):
        data = msg.data
        self.logger.info(msg.short())
        try:
            if data.com == 'welcome':
                if data.info.device_id in self.parent.connections:
                    self.logger.info(f'Server {data.info.device_id} is active. Handshake was undertaken')
                    del self.demands_pending_answer[msg.reply_to]
                    connection: Connection = self.parent.connections[data.info.device_id]
                    connection.device_info = data.info
        except KeyError as e:
            self.logger.error(e)

    def react_demand(self, msg: Message):
        pass


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

    def react_info(self, msg: Message):
        data = msg.data
        # TODO: if section should be added to check weather device which send cmd is in connections or not
        # at this moment connections is dict with key = device_id
        if 'heartbeat' in data.com:
            try:
                self.events[data.info.event_id].time = time()
                self.events[data.info.event_id].n = data.info.n
            except KeyError as e:
                self.logger.error(e)
        elif data.com == 'shutdown':
            # TODO: the info is not deleted from _frontend sockets or backend sockets
            self.remove_device_from_connections(data.info.device_id)

    def react_demand(self, msg: Message):
        data = msg.data
        cmd = data.com
        info_msg(self, 'REQUEST', extra=str(msg))
        reply = True
        if cmd == 'check_service':
            service_name = data.info.service_name
            services_running = self.messenger.parent.services_running
            key_s = None
            for key in enumerate(services_running.keys()):
                if service_name in key[1]:
                    key_s = key[1]
                    break
            if key_s:
                service = services_running[key_s]
            else:
                service = None
            msg_i = gen_msg('status_service', self.messenger, msg_i=msg, service=service)
        elif cmd == 'on_service':
            service_name = data.info.service_name
            services_running = self.messenger.parent.services_running
            key_s = None
            for key in enumerate(services_running.keys()):
                if service_name in key[1]:
                    key_s = key[1]
                    break
            if key_s:
                service = services_running[key_s]
                service.turn_on()
            else:
                service = None
            msg_i = gen_msg('status_service', self.messenger, msg_i=msg, service=service)
        elif cmd == 'hello':
            try:
                device_info: DeviceInfoMes = data.info
                connections = self.parent.connections
                if data.info.type not in ('service', 'client'):
                    raise Exception(f'{self}:{device_info.type} is not known')

                if device_info.device_id not in connections:
                    connections[device_info.device_id] = Connection(device_info=data.info)
                    if 'publisher' in device_info.messenger_info.public_sockets:
                        from communication.logic.logic_functions import external_hb_logic
                        self.parent.messenger.subscribe_sub(address=device_info.messenger_info.public_sockets['publisher'])
                        a = f'heartbeat:{data.info.name}'
                        self.register_event(name=f'heartbeat:{data.info.name}',
                                            logic_func=external_hb_logic,
                                            event_id=f'heartbeat:{data.info.device_id}',
                                            original_owner=device_info.device_id,
                                            start_now=True)
                    msg_i = gen_msg('welcome', device=self.parent, msg_i=msg)
                    if self.parent.pyqtsignal_connected:
                        msg_i_GUI = gen_msg(com='status_server_full', device=self.parent)
                        self.parent.signal.emit(msg_i_GUI)
                else:
                    msg_i = gen_msg('welcome', device=self.parent, msg_i=msg)
            except Exception as e:
                self.logger.error(e)
                msg_i = gen_msg('error_message', device=self.parent, comments=repr(e), msg_i=msg)
        elif cmd == 'available_services':
            # from communication.logic.logic_functions import postponed_reaction
            msg_i = gen_msg('available_services_reply', device=self.parent, msg_i=msg)
            # postponed_reaction(self.add_task_out, msg_i, 12, self.logger)
            # reply = False
        else:
            msg_i = gen_msg('unknown_message', device=self.parent, msg_i=msg)
        if reply:
            info_msg(self, 'REPLY', extra=repr(msg_i))
            self.add_task_out(msg_i)

    def react_reply(self,  msg: Message):
        pass

    def react_unknown(self, msg: Message):
        msg_i = gen_msg('unknown_message', self.messenger, msg_i=msg)
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
                self.parent.send_status_pyqt()
        else:
            self.logger.info(f'react_internal: I do not know what to do, {event.name} is not known')


class SuperUserClientCmdLogic(GeneralCmdLogic):


    def react_info(self, msg: Message):
        super().react_info(msg)

    def react_internal(self, event: ThinkerEvent):
        super().react_internal(event)

    def react_unknown(self, msg: Message):
        super().react_unknown(msg)

    def react_demand(self, msg: Message):
        super().react_demand(msg)

    def react_reply(self, msg: Message):
        super().react_reply(msg)
        data = msg.data
        if data.com == 'welcome':
            msg = gen_msg('available_services', device=self.parent)
            self.add_task_out(msg)
        elif data.com == 'available_services_reply':
            if self.parent.pyqtsignal_connected:
                self.parent.signal.emit(msg)
            del self.demands_pending_answer[msg.reply_to]


class StpMtrCmdLogic(GeneralCmdLogic):
    pass


class StpMtrClientCmdLogic(StpMtrCmdLogic):

    pass


class StpMtrCtrlServiceCmdLogic(StpMtrCmdLogic):
    pass

