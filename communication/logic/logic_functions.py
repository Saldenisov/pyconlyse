from threading import Thread
from time import sleep, time
from typing import Callable

from communication.logic.thinkers_logic import Thinker, ThinkerEvent
from communication.messaging.messages import MessageExt, MsgComInt, MsgComExt
from devices.interfaces import DeviceType
from utilities.datastructures.mes_dependent.dicts import MsgDict
from utilities.datastructures.mes_dependent.general import PendingReply
from utilities.errors.myexceptions import ThinkerErrorReact
from utilities.myfunc import info_msg, error_logger


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
            if full_heartbeat and event.n % 3:
                # TODO: every n minutes changes session_key for safety...
                msg_heartbeat = device.generate_msg(msg_com=MsgComExt.HEARTBEAT_FULL, event=event)
            else:
                msg_heartbeat = device.generate_msg(msg_com=MsgComExt.HEARTBEAT, event=event)

            if device.pyqtsignal_connected and device.type is DeviceType.SERVER:
                msg = device.generate_msg(msg_com=MsgComInt.HEARTBEAT, event=event)
                device.signal.emit(msg)

            thinker.add_task_out(msg_heartbeat)
            sleep(event.tick)


def internal_info_logic(event: ThinkerEvent):
    # TODO: why I need it?
    thinker: Thinker = event.parent
    device = thinker.parent
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    while event.active:
        sleep(0.001)
        if not event.paused:
            sleep(event.tick)
            # TODO': requires update


def task_in_reaction(event: ThinkerEvent):
    thinker: Thinker = event.parent
    tasks_in: MsgDict = thinker.tasks_in
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    exclude_msgs = [MsgComExt.HEARTBEAT.msg_name, MsgComExt.HEARTBEAT_FULL.msg_name]
    while event.active:
        sleep(0.001)  # Any small interruption is necessary not to overuse processor time
        if not event.paused and tasks_in:
            try:
                msg: MessageExt = tasks_in.popitem(last=False)[1]
                thinker.msg_counter += 1
                react = True
                if msg.com not in exclude_msgs:
                    pass
                    #info_msg(event, 'INFO', f'Received: {msg.short()}')

                if msg.reply_to == '' and msg.receiver_id != '':  # If message is not a reply, it must be a demand one
                    thinker.add_demand_waiting_reply(msg)
                    #info_msg(event, 'INFO', f'Expect a reply to {msg.id} com={msg.com}. Adding to waiting list.')

                elif msg.reply_to != '':
                    if msg.reply_to in thinker.demands_waiting_reply:
                        # TODO: should it have else clause or not?
                        msg_awaited: MessageExt = thinker.demands_waiting_reply[msg.reply_to].message
                        del thinker.demands_waiting_reply[msg.reply_to]
                        #info_msg(event, 'INFO', f'REPLY to Msg {msg.reply_to} {msg_awaited.com} is obtained.')
                    elif msg.reply_to == 'delayed_response':
                        pass
                    else:
                        react = False
                        info_msg(event, 'INFO', f'Reply to msg {msg.reply_to} arrived too late.')
                if react:
                    thinker.react_external(msg)
            except (ThinkerErrorReact, KeyError, RuntimeError) as e:
                error_logger(event, task_in_reaction, f'{e}: {msg.short()}')


def task_out_reaction(event: ThinkerEvent):
    thinker: Thinker = event.parent
    tasks_out: MsgDict = thinker.tasks_out
    demand_waiting_reply: MsgDict = thinker.demands_waiting_reply
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    while event.active:
        sleep(0.001)
        if not event.paused and tasks_out:
            try:
                msg: MessageExt = tasks_out.popitem(last=False)[1]
                react = True
                if msg.receiver_id != '' and msg.reply_to == '':
                    # If msg is not reply, than add to pending demand
                    #info_msg(event, 'INFO', f'Msg id={msg.id}, com {msg.com} is considered to get a reply')
                    thinker.add_demand_waiting_reply(msg)

                elif msg.reply_to != '':
                    if msg.reply_to in demand_waiting_reply:
                        msg_awaited: MessageExt = thinker.demands_waiting_reply[msg.reply_to].message
                        del demand_waiting_reply[msg.reply_to]
                        #info_msg(event, 'INFO', f'Msg id={msg.reply_to} {msg_awaited.com} is deleted from demand_waiting_reply')
                if react:
                    thinker.parent.messenger.add_msg_out(msg)
            except (ThinkerErrorReact, KeyError, RuntimeError) as e:
                error_logger(event, task_out_reaction, f'{e}: {msg.short()}')


def pending_demands(event: ThinkerEvent): 
    thinker: Thinker = event.parent
    demands_waiting_reply: MsgDict = thinker.demands_waiting_reply
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    while event.active:
        sleep(0.001)
        if not event.paused and demands_waiting_reply:
            try:
                sleep(event.tick)
                for key, item in demands_waiting_reply.items():
                    pending: PendingReply = item
                    if (time() - event.time) > event.tick and pending.attempt < 3:
                        pending.attempt += 1
                        info_msg(event, 'INFO', f'Msg {pending.message.id}, com {pending.message.com} waits '
                                                f'{pending.attempt}.')
                    elif (time() - event.time) > event.tick and pending.attempt >= 3:
                        try:
                            msg = pending.message
                            del demands_waiting_reply[key]
                            info_msg(event, 'INFO', f'Reply timeout for msg: {msg.short()}')
                            info_msg(event, 'INFO', f'Msg {msg.id} is deleted')
                        except KeyError:
                            error_logger(event, pending_demands, f'Cannot delete Msg {msg.id}, com {msg.com} from '
                                                                 f'demand_waiting_reply')
            except (ThinkerErrorReact, RuntimeError) as e:
                error_logger(event, pending_demands, e)


def postponed_reaction(replier: Callable[[MessageExt], None], reaction: MessageExt, t: float=1.0, logger=None):
    # TODO: why it is needed in the first place?
    def f():
        if logger:
            logger.info(f'Postponed_reaction for {reaction.short()} started')
        sleep(t)
        replier(reaction)
    trd = Thread(target=f)
    trd.start()
