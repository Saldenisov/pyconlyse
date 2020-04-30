from time import sleep, time
from threading import Thread
from typing import Callable

from communication.logic.thinkers_logic import Thinker, ThinkerEvent
from devices.interfaces import DeviceType
from utilities.errors.myexceptions import ThinkerErrorReact
from datastructures.mes_dependent.dicts import OrderedDictMod
from utilities.data.datastructures.mes_dependent.general import PendingReply
from utilities.data.messaging.messages import MessageExt, MsgType, MsgComInt, MsgComExt
from utilities.myfunc import info_msg, error_logger


def external_hb_logic(event: ThinkerEvent):
    """
    This event function is designed to track after external events, e.g., heartbeat of a Server
    If event is timeout, than counter_timeout += 1
    Every cycle event is being send to Thinker.react_internal, where Thinker decides what should be done, if, e.g.,
    counter_timeout reached certain value
    Every event.print_every_n the information of event is printed out in console
    :param event: ThinkerEvent
    :return: None
    """

    thinker: Thinker = event.parent
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    counter = 0
    while event.active:
        if not event.paused:
            sleep(event.tick)
            if (time() - event.time) >= event.tick:
                event.counter_timeout += 1
                thinker.logger.info(f'{event.name} timeout {event.counter_timeout}')
            else:
                event.counter_timeout = 0
            counter += 1
            event.parent.react_internal(event)
            if counter % event.print_every_n == 0:
                counter = 0
                info_msg(event, 'INFO', extra=f'{event.name} : {event.n}')
        else:
            sleep(0.05)
            event.time = time()


def internal_hb_logic(event: ThinkerEvent):
    thinker: Thinker = event.parent
    device = thinker.parent
    interchange = False
    if device.type is DeviceType.SERVER:
        interchange = True
    info_msg(event, 'STARTED', extra=f' of {thinker.name}')
    while event.active:
        if not event.paused:
            event.n += 1
            sleep(event.tick)
            if interchange and event.n % 2:
                msg_heartbeat = device.generate_msg(msg_com=MsgComExt.HEARTBEAT_FULL, event=event)
            else:
                msg_heartbeat = device.generate_msg(msg_com=MsgComExt.HEARTBEAT, event=event)

            if device.pyqtsignal_connected:
                msg = device.generate_msg(msg_com=MsgComInt.HEARTBEAT, event=event)
                device.signal.emit(msg)

            thinker.add_task_out(msg_heartbeat)
        else:
            sleep(0.05)


def internal_info_logic(event: ThinkerEvent):
    thinker: Thinker = event.parent
    device = thinker.parent
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    while event.active:
        if not event.paused:
            sleep(event.tick)
            # TODO': requires update
            #msg = MsgGenerator.degen_msg('device_info_short', device, event=event)
            #thinker.add_task_out(msg)
        else:
            sleep(0.05)


def task_in_reaction(event: ThinkerEvent):
    thinker: Thinker = event.parent
    tasks: OrderedDictMod = thinker.tasks_in
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    while event.active:
        if not event.paused:
            sleep(event.tick)
            if tasks:
                try:
                    msg: MessageExt = tasks.popitem()[1]
                    thinker.msg_counter += 1

                    if msg.type is MsgType.DEMAND:
                        thinker.add_reply_pending(msg)

                    if msg.reply_to in thinker.demands_pending_answer:
                        # TODO: should it else clause
                        del thinker.demands_pending_answer[msg.reply_to]
                        event.logger.info(f'react_reply: Msg {msg.reply_to} reply is obtained')

                    if msg.type in MsgType:
                        info_msg(event, msg.type, extra=str(msg.short()))
                        thinker.react_external(msg)
                    else:
                        raise ThinkerErrorReact(f'Message type has wrong value {msg.type}')

                except ThinkerErrorReact as e:
                    error_logger(event, task_in_reaction, f'{e}: {msg}')
        else:
            sleep(0.05)


def task_out_reaction(event: ThinkerEvent):
    thinker: Thinker = event.parent
    tasks: OrderedDictMod = thinker.tasks_out
    tasks_reply_pending: OrderedDictMod = thinker.replies_pending_answer
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    react = True
    while event.active:
        if not event.paused:
            sleep(event.tick)
            if tasks:
                try:
                    msg: MessageExt = tasks.popitem()[1]
                    if msg.type == 'demand':
                        thinker.add_demand_pending(msg)
                    elif msg.type == 'reply':
                        if msg.reply_to in tasks_reply_pending:
                            react = True
                            try:
                                del tasks_reply_pending[msg.reply_to]
                                event.logger.info(f'Message {msg.reply_to} is deleted from tasks_reply_pending')
                            except KeyError as e:
                                event.logger.error(e)
                        else:
                            react = False
                            event.logger.info(f'Timeout for message {msg}')
                    elif msg.type == 'info':
                        react = True
                    if react:
                        thinker.parent.send_msg_externally(msg)
                except ThinkerErrorReact as e:
                    error_logger(event, task_out_reaction, f'{e}: {msg}')
        else:
            sleep(0.05)


def pending_demands(event: ThinkerEvent):
    thinker: Thinker = event.parent
    tasks: OrderedDictMod = thinker.demands_pending_answer
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    while event.active:
        if not event.paused:
            sleep(event.tick)
            if tasks:
                print(f'Pending demands number of tasks {len(tasks)}')
                try:
                    for key, item in tasks.items():
                        pending: PendingReply = item
                        if (time() - event.time) > event.tick and pending.attempt < 3:
                            #thinker.react_out(pending.message)
                            pending.attempt = pending.attempt + 1
                            thinker.logger.info(f'Pending message awaits {pending.attempt}: {pending.message}')
                        elif (time() - event.time) > event.tick and pending.attempt >= 3:
                            try:
                                msg = pending.message
                                del tasks[key]
                                event.logger.error(f'Timeout for demand msg: {msg}')
                                event.logger.info(f'Msg: {msg.id} is deleted')
                            except KeyError:
                                info_msg(event, event.run, f'Cannot delete msg: {msg.reply_to} from pending_demands')
                except ThinkerErrorReact as e:
                    error_logger(event, event.run, e)
        else:
            sleep(0.05)


def pending_replies(event: ThinkerEvent):
    thinker: Thinker = event.parent
    device = thinker.parent
    tasks: OrderedDictMod = thinker.replies_pending_answer
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    while event.active:
        if not event.paused:
            sleep(event.tick)
            if tasks:
                try:
                    for key, item in tasks.items():
                        pending: PendingReply = item
                        if (time() - event.time) > event.tick and pending.attempt < 3:
                            pending.attempt = pending.attempt + 1
                            thinker.logger.info(f'Pending reply message waits {pending.attempt}: {pending.message}')
                        elif (time() - event.time) > event.tick and pending.attempt >= 3:
                            try:
                                # TODO: xxxx including correct error msg comments
                                msg = pending.message
                                msg_out = MsgGenerator.error(device=device, msg_i=msg, comments='timeout')
                                thinker.add_task_out(msg_out)
                                del tasks[key]
                                event.logger.error(f'Timeout for reply msg: {msg}')
                                event.logger.info(f'Msg: {msg.id} is deleted')
                            except KeyError:
                                error_logger(event, event.run, f'Cannot delete msg: {msg.reply_to} from pending_replies')
                except ThinkerErrorReact as e:
                    error_logger(event, event.run, e)
        else:
            sleep(0.05)


def postponed_reaction(replier: Callable[[MessageExt], None], reaction: MessageExt, t: float=1.0, logger=None):
    def f():
        if logger:
            logger.info(f'Postponed_reaction for {reaction.short()} started')
        sleep(t)
        replier(reaction)
    trd = Thread(target=f)
    trd.start()
