import logging
from abc import abstractmethod
from threading import Thread
from time import time
from typing import Callable, List, Union
from communication.interfaces import ThinkerInter
from utilities.errors.myexceptions import *
from communication.messaging.messages import MessageExt, MsgComExt
from datastructures.mes_dependent.dicts import Events_Dict, MsgDict
from datastructures.mes_dependent.general import PendingDemand, PendingReply
from utilities.myfunc import info_msg, error_logger, unique_id

module_logger = logging.getLogger(__name__)


class Thinker(ThinkerInter):

    n_instance = 0

    def __init__(self, parent):
        from devices.devices import Device
        Thinker.n_instance += 1
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)
        self.name = f'{self.__class__.__name__}:{parent.name}:{Thinker.n_instance}'
        self.id = f'{self.name}:{unique_id(self.name)}'
        self.parent: Device = parent
        self.msg_counter = 0
        self.events = Events_Dict()
        msg_dict_size_limit = 10000
        self._tasks_in = MsgDict(name='tasks_in', size_limit=msg_dict_size_limit, dict_parent=self)
        self.tasks_in_test = MsgDict(name='tasks_in_test', size_limit=msg_dict_size_limit, dict_parent=self)
        self._tasks_out = MsgDict(name='tasks_out', size_limit=msg_dict_size_limit, dict_parent=self)
        self.tasks_out_test = MsgDict(name='tasks_out_test', size_limit=msg_dict_size_limit, dict_parent=self)
        self._demands_waiting_reply = MsgDict(name='demands_waiting_reply', size_limit=msg_dict_size_limit,
                                              dict_parent=self)
        # TODO: add slow thread to track after forwarded messages
        self._forwarded = MsgDict(name='forwarded_messages', size_limit=msg_dict_size_limit, dict_parent=self)
        self.paused = False

        info_msg(self, 'CREATING')
        try:
            self.timeout = int(self.parent.get_general_settings()['timeout'])
            pending_demands_tick = float(self.parent.get_general_settings()['pending_demands']) / 1000.
        except KeyError as e:
            error_logger(self, self.__init__, e)
            self.timeout = 10
            pending_demands_tick = 0.2
        try:
            from communication.logic.logic_functions import (task_in_reaction, task_out_reaction, pending_demands)
            self.register_event(name='task_in_reaction', logic_func=task_in_reaction, tick=None)
            self.register_event(name='task_out_reaction', logic_func=task_out_reaction, tick=None)
            self.register_event(name='demands_waiting_reply', logic_func=pending_demands, tick=pending_demands_tick)
            info_msg(self, 'CREATED')
        except (ThinkerEventError, ThinkerEventFuncError, TypeError) as e:
            error_logger(self, self.register_event, e)
            info_msg(self, 'NOT CREATED')
            raise ThinkerError(str(e))

    def add_task_in(self, msg: MessageExt):
        try:
            self._tasks_in[msg.id] = msg
            if self.parent.test and not (msg.com == MsgComExt.HEARTBEAT.msg_name):
                self.tasks_in_test[msg.id] = msg
        except KeyError as e:
            error_logger(self, self.add_task_in, e)
            raise e

    def add_task_out(self, msg: MessageExt):
        try:
            self._tasks_out[msg.id] = msg
            if self.parent.test and not (msg.com == MsgComExt.HEARTBEAT.msg_name):
                self.tasks_out_test[msg.id] = msg
        except KeyError as e:
            error_logger(self, self.add_task_out, e)

    def add_demand_waiting_reply(self, msg: MessageExt):
        try:
            self._demands_waiting_reply[msg.id] = PendingDemand(message=msg)
        except KeyError as e:
            error_logger(self, self.add_demand_waiting_reply, e)

    def add_to_forwarded(self, msg_forwarded: MessageExt, msg_arrived: MessageExt):
        try:
            self._forwarded[msg_forwarded.id] = msg_arrived
        except KeyError as e:
            error_logger(self, self.add_demand_waiting_reply, e)

    def info(self):
        from collections import OrderedDict as od
        info = od()
        info['id'] = self.id
        info['events'] = self.events
        info['tasks_in'] = self.tasks_in
        info['tasks_out'] = self.tasks_out
        info['pending_clients_demands'] = self.clients_demands_pending_answer
        info['pending_replies'] = self.pending_replies
        return info

    def msg_out(self, msg_out: Union[MessageExt, List[MessageExt]]):
        if msg_out:
            if isinstance(msg_out, list):
                for msg in msg_out:
                    self.msg_out(msg)
            elif isinstance(msg_out, MessageExt):
                info_msg(self, 'INFO', extra=repr(msg_out.short()))
                self.add_task_out(msg_out)
            else:
                error_logger(self, self.msg_out, f'Union[MessageExt, List[MessageExt]] was not passed to msg_out, but'
                                                 f'{msg_out}')

    def register_event(self, name: str, logic_func: Callable, event_id='', external_name='', original_owner='',
                       start_now=False, **kwargs):
        # TODO: to complicated. Need to optimize.
        try:
            if 'tick' in kwargs:
                tick = kwargs['tick']
            else:
                tick = float(self.parent.get_general_settings()[name.split(':')[0]]) / 1000
        except KeyError as e:
            error_logger(self, self.register_event, f'{e}. Tick value is set to {tick}s')
        finally:
            print_every_n = int(self.parent.get_general_settings()['print_every_n'])
            try:
                if not external_name:
                    external_name = name
                if not event_id:
                    event_id = f'{external_name}:{self.parent.id}'
                if original_owner == '':
                    original_owner = self.parent.id
                self.events[event_id] = ThinkerEvent(name=name,
                                                     external_name=external_name,
                                                     parent=self,
                                                     logic_func=logic_func,
                                                     tick=tick,
                                                     print_every_n=print_every_n,
                                                     event_id=event_id,
                                                     original_owner=original_owner)

                if start_now:
                    self.events[event_id].start()

            except ThinkerEventFuncError as e:
                raise ThinkerEventError(str(e))

    @property
    def demands_waiting_reply(self) -> MsgDict:
        return self._demands_waiting_reply

    @property
    def forwarded_messages(self) -> MsgDict:
        return self._forwarded

    @abstractmethod
    def react_external(self, msg: MessageExt):
        pass

    @abstractmethod
    def react_broadcast(self, msg: MessageExt):
        pass

    @abstractmethod
    def react_forward(self, msg: MessageExt):
        pass

    @abstractmethod
    def react_first_welcome(self, msg: MessageExt):
        pass

    @abstractmethod
    def react_heartbeat_full(self, msg: MessageExt):
        pass

    @abstractmethod
    def react_directed(self, msg: MessageExt):
        pass

    @abstractmethod
    def react_internal(self, event):
        pass

    def remove_device_from_connections(self, device_id):
        # TODO: the info is not deleted from _frontend sockets or backend sockets
        connections = self.parent.connections
        if device_id in connections:
            info_msg(self, 'INFO', f'Procedure to delete {device_id} is started')
            for key, event in list(self.events.items()):
                if event.original_owner == device_id:
                    self.unregister_event(key)
            del self.parent.connections[device_id]
            info_msg(self, 'INFO', f'Device {device_id} is deleted')
        else:
            error_logger(self, self.remove_device_from_connections,
                         f'remove_device_from_connections: Wrong device_id {device_id} is passed')

    @property
    def tasks_in(self) -> MsgDict:
        return self._tasks_in

    @property
    def tasks_out(self) -> MsgDict:
        return self._tasks_out

    def start(self):
        info_msg(self, 'STARTING')
        for _, event in self.events.items():
            if not event.active:
                event.start()

    def stop(self):
        info_msg(self, 'STOPPING')
        for event_id, event in self.events.items():
            event.stop()
        self.events = Events_Dict()

    def pause(self):
        self.paused = True
        if self.events:
            for _, event in self.events.items():
                event.pause()

    def unpause(self):
        self.paused = False

        if self.events:
            for _, event in self.events.items():
                event.unpause()

    def unregister_event(self, event_id: str):
        if event_id in self.events:
            self.events[event_id].stop()
            del self.events[event_id]


class ThinkerEvent(Thread):
    def __init__(self, name: str, external_name: str, event_id: str, logic_func: Callable, parent: Thinker, tick=0.1,
                 print_every_n=20, original_owner=''):
        super().__init__()
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)
        self.name = name
        self.external_name = external_name
        self.id = event_id
        self.parent = parent
        self.original_owner = original_owner
        self.logic_func = logic_func
        self.print_every_n = print_every_n
        self.n = 0  # reserved for heartbeat events
        self.time = 0
        self.tick = tick  # in sec
        self.active = False
        self.paused = False
        self.counter_timeout = 0
        if self.parent:
            info_msg(self, 'CREATED', extra=f' of {self.parent.name}')
        else:
            info_msg(self, 'CREATED')

    def run(self):
        self.active = True
        self.paused = self.parent.paused
        try:
            self.time = time()
            info_msg(self, 'STARTING', extra=f' of {self.parent.name}')
            self.logic_func(self)
        except Exception as e:
            error_logger(self, self.run, f'{self.name}. Error: {e}')
        finally:
            info_msg(self, 'STOPPED', extra=f' of {self.parent.name}')


    def stop(self):
        info_msg(self, 'STOPPING', extra=f' of {self.parent.name}')
        self.active = False

    def pause(self):
        info_msg(self, 'PAUSING')
        self.paused = True
        info_msg(self, 'PAUSED')

    def unpause(self):
        info_msg(self, 'UNPAUSING')
        self.paused = False
        info_msg(self, 'UNPAUSED')
