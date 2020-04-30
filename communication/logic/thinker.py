import logging
from abc import abstractmethod
from threading import Thread
from time import time
from typing import Callable, List, Union
from communication.interfaces import ThinkerInter
from utilities.errors.myexceptions import *
from utilities.data.messaging.messages import MessageExt, MsgComExt
from datastructures.mes_dependent.dicts import Events_Dict, OrderedDictMod, OrderedDictMesTypeCounter
from utilities.data.datastructures.mes_dependent.general import PendingDemand, PendingReply
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
        self._tasks_in = OrderedDictMod(name='tasks_in')
        self.tasks_in_test = OrderedDictMod(name='tasks_in_test')
        self._tasks_out = OrderedDictMod(name='tasks_out')
        self.tasks_out_test = OrderedDictMod(name='tasks_out_test')
        self._pending_demands = OrderedDictMesTypeCounter(name='pending_demands')
        self._pending_replies = OrderedDictMesTypeCounter(name='pending_replies')
        self.paused = False

        info_msg(self, 'CREATING')
        try:
            self.timeout = int(self.parent.get_general_settings()['timeout'])
            task_in_reaction_tick = float(self.parent.get_general_settings()['task_in_reaction']) / 1000.
            task_out_reaction_tick = float(self.parent.get_general_settings()['task_out_reaction']) / 1000.
            pending_demands_tick = float(self.parent.get_general_settings()['pending_demands']) / 1000.
            pending_replies_tick = float(self.parent.get_general_settings()['pending_replies']) / 1000.
        except KeyError as e:
            error_logger(self, self.__init__, e)
            self.timeout = 10
            task_in_reaction_tick = 0.001
            task_out_reaction_tick = 0.001
            pending_demands_tick = 0.2
        try:
            from communication.logic.logic_functions import (task_in_reaction, task_out_reaction, pending_demands,
                                                             pending_replies)
            self.register_event(name='task_in_reaction', logic_func=task_in_reaction, tick=task_in_reaction_tick)
            self.register_event(name='task_out_reaction', logic_func=task_out_reaction, tick=task_out_reaction_tick)
            self.register_event(name='pending_demands', logic_func=pending_demands, tick=pending_demands_tick)
            self.register_event(name='pending_replies', logic_func=pending_replies, tick=pending_replies_tick)
            info_msg(self, 'CREATED')
        except (ThinkerEventError, ThinkerEventFuncError, TypeError) as e:
            error_logger(self, self.register_event, e)
            info_msg(self, 'NOT CREATED')
            raise ThinkerError(str(e))

    def add_task_in(self, msg: MessageExt):
        try:
            if len(self._tasks_in) > 10000:
                self._tasks_in.popitem()  # pop up first item
            self._tasks_in[msg.id] = msg
            if self.parent.test and not (msg.com == MsgComExt.HEARTBEAT.name):
                self.tasks_in_test[msg.id] = msg
        except KeyError as e:
            error_logger(self, self.add_task_in, e)
            raise e

    def add_task_out(self, msg: MessageExt):
        try:
            if len(self._tasks_out) > 10000:
                self._tasks_out.popitem()  # pop up first item
            self._tasks_out[msg.id] = msg
            if self.parent.test and not (msg.com == MsgComExt.HEARTBEAT.name):
                self.tasks_out_test[msg.id] = msg
        except KeyError as e:
            error_logger(self, self.add_task_out, e)
            raise e

    def add_demand_pending(self, msg: MessageExt):
        try:
            if len(self._pending_demands) > 10000:
                self._pending_demands.popitem()  # pop up first item
            self._pending_demands[msg.id] = PendingDemand(message=msg)
        except KeyError as e:
            info_msg(self, self.add_demand_pending, e)

    def add_reply_pending(self, msg: MessageExt):
        try:
            if len(self._pending_replies) > 10000:
                self._pending_replies.popitem()  # pop up first item
            self._pending_replies[msg.id] = PendingReply(message=msg)
        except KeyError as e:
            info_msg(self, self.add_demand_pending, e)

    @property
    def demands_pending_answer(self) -> OrderedDictMod:
        return self._pending_demands

    def info(self):
        from collections import OrderedDict as od
        info = od()
        info['id'] = self.id
        info['events'] = self.events
        info['tasks_in'] = self.tasks_in
        info['tasks_out'] = self.tasks_out
        info['pending_demands'] = self.demands_pending_answer
        info['pending_replies'] = self.replies_pending_answer
        return info

    def msg_out(self, out: bool, msg_i: Union[MessageExt, List[MessageExt]]):
        if out and msg_i:
            if isinstance(msg_i, list):
                for msg in msg_i:
                    self.msg_out(out, msg)
            elif isinstance(msg_i, MessageExt):
                info_msg(self, 'INFO', extra=repr(msg_i.short()))
            else:
                self.add_task_out(msg_i)

    def register_event(self, name: str, logic_func: Callable, event_id='', external_name='', original_owner='',
                       start_now=False, **kwargs):
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
    def replies_pending_answer(self) -> OrderedDictMod:
        return self._pending_replies

    @abstractmethod
    def react_internal(self, event):
        pass

    @abstractmethod
    def react_external(self, msg: MessageExt):
        pass

    @abstractmethod
    def react_unknown(self, msg: MessageExt):
        pass

    def remove_device_from_connections(self, device_id):
        # TODO: the info is not deleted from _frontend sockets or backend sockets
        connections = self.parent.connections
        if device_id in connections:
            self.logger.info(f'Procedure to delete {device_id} is started')
            for key, event in list(self.events.items()):
                if event.original_owner == device_id:
                    self.unregister_event(key)
            del self.parent.connections[device_id]
            self.logger.info(f'Device {device_id} is deleted')
        else:
            error_logger(self, self.remove_device_from_connections,
                         f'remove_device_from_connections: Wrong device_id {device_id} is passed')

    @property
    def tasks_in(self) -> OrderedDictMod:
        return self._tasks_in

    @property
    def tasks_out(self) -> OrderedDictMod:
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
        self.events = {}

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
        info_msg(self, 'CREATED', extra=f' of {self.parent.name}')

    def run(self):
        self.active = True
        self.paused = self.parent.paused
        try:
            self.time = time()
            info_msg(self, 'STARTING', extra=f' of {self.parent.name}')
            self.logic_func(self)
        except Exception as e:
            error_logger(self, self.run, e)
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
