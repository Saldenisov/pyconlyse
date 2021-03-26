from copy import deepcopy
from threading import Thread
from time import sleep, time
from typing import Callable
from communication.logic.thinkers_logic import ServerCmdLogic
from communication.logic.thinkers_logic import Thinker, ThinkerEvent
from communication.messaging.messages import MessageExt, MsgComInt, MsgComExt
from devices.interfaces import DeviceType
from utilities.datastructures.mes_dependent.dicts import MsgDict
from utilities.datastructures.mes_dependent.general import PendingReply
from utilities.errors.myexceptions import ThinkerErrorReact
from utilities.myfunc import info_msg as i_msg
from utilities.myfunc import error_logger
from utilities.tools.decorators import turn_off


@turn_off(active=False)
def info_msg(*args, **kwargs):
    return i_msg(*args, **kwargs)


def external_hb_logic(event: ThinkerEvent):
    """
    This event function is designed to track after external events, e.g., heartbeat of a Server
    If event is timeout, than counter_timeout += 1
    Every cycle event is being send to Thinker.react_internal, where Thinker decides what should be done, e.g.,
    counter_timeout reached certain value
    Every event.print_every_n the information of event is printed out in console
    :param event: ThinkerEvent
    :return: None
    """
    thinker: Thinker = event.parent
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    counter = 0
    while event.active:
        sleep(0.001)
        if not event.paused:
            sleep(event.tick)
            if (time() - event.time) >= event.tick:
                event.counter_timeout += 1
            else:
                event.counter_timeout = 0

            if event.counter_timeout % 3 == 0 and event.counter_timeout != 0:
                info_msg(event, 'INFO', f'{event.name} timeout {event.counter_timeout}')

            counter += 1
            event.parent.react_internal(event)

            if counter % event.print_every_n == 0:
                counter = 0
                info_msg(event, 'INFO', extra=f'{event.name}: {event.n}')
        else:
            sleep(0.05)
            event.time = time()


def internal_hb_logic(event: ThinkerEvent):
    thinker: Thinker = event.parent
    device = thinker.parent
    full_heartbeat = False
    if device.type is DeviceType.SERVER:
        full_heartbeat = True  # Allows to send MsgComExt.HEARTBEAT_FULL only for Server
    info_msg(event, 'STARTED', extra=f' of {thinker.name}')
    while event.active:
        sleep(0.001)
        if not event.paused:
            event.n += 1
            if full_heartbeat and event.n % 3 and device.type is DeviceType.SERVER:
                # TODO: every n minutes changes session_key for safety...that is crazy
                msg_heartbeat = device.generate_msg(msg_com=MsgComExt.HEARTBEAT_FULL, event=event)
            else:
                msg_heartbeat = device.generate_msg(msg_com=MsgComExt.HEARTBEAT, event=event)

            if device.pyqtsignal_connected and device.type is DeviceType.SERVER:
                msg = device.generate_msg(msg_com=MsgComInt.HEARTBEAT, event=event)
                device.signal.emit(msg)

            thinker.add_task_out_publisher(msg_heartbeat)
            sleep(event.tick)


def task_in_reaction(event: ThinkerEvent):
    thinker: Thinker = event.parent
    tasks_in: MsgDict = thinker.tasks_in
    demand_on_reply: MsgDict = thinker.demands_on_reply
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    exclude_msgs = [MsgComExt.HEARTBEAT.msg_name, MsgComExt.HEARTBEAT_FULL.msg_name]
    while event.active:
        sleep(0.001)  # Any small interruption is necessary not to overuse processor time
        if not event.paused and tasks_in:
            msg: MessageExt = tasks_in.popitem(last=False)[1]
            thinker.msg_counter += 1
            try:
                if msg.com not in exclude_msgs:
                    if thinker.parent.pyqtsignal_connected:
                        # Convert MessageExt to MessageInt and emit it
                        msg_int = msg.fyi()
                        thinker.parent.signal.emit(msg_int)
                    if msg.reply_to in demand_on_reply:
                        text = 'Received reply'
                    else:
                        text = 'Received'
                    info_msg(event, 'INFO', f'{text}: {msg.short()}')
                thinker.react_external(msg)
            except (ThinkerErrorReact, KeyError, RuntimeError, Exception) as e:
                error_logger(event, task_in_reaction, f'{e}: {msg.short()}')


def task_out_reaction(event: ThinkerEvent):
    thinker: Thinker = event.parent
    tasks_out: MsgDict = thinker.tasks_out
    tasks_out_publisher: MsgDict = thinker.tasks_out_publihser
    demand_on_reply: MsgDict = thinker.demands_on_reply
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    while event.active:
        sleep(0.001)
        if not event.paused and (tasks_out or tasks_out_publisher):
            try:
                if tasks_out:
                    msg: MessageExt = tasks_out.popitem(last=False)[1]
                    thinker.add_demand_on_reply(msg)
                    thinker.parent.messenger.add_msg_out(msg)

                    if thinker.parent.pyqtsignal_connected:
                        # Convert MessageExt to MessageInt and emit it
                        msg_int = msg.fyi()
                        thinker.parent.signal.emit(msg_int)

                if tasks_out_publisher:
                    msg: MessageExt = tasks_out_publisher.popitem(last=False)[1]
                    thinker.parent.messenger.add_msg_out_publisher(msg)

            except (ThinkerErrorReact, KeyError, RuntimeError) as e:
                error_logger(event, task_out_reaction, f'{e}: {msg.short()}')
