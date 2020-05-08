from time import sleep, time
from threading import Thread
from typing import Callable

from communication.logic.thinkers_logic import Thinker, ThinkerEvent
from communication.messaging.messages import MessageExt, MsgType, MsgComInt, MsgComExt
from devices.interfaces import DeviceType
from datastructures.mes_dependent.dicts import MsgDict
from datastructures.mes_dependent.general import PendingReply
from utilities.myfunc import info_msg, error_logger
from utilities.errors.myexceptions import ThinkerErrorReact


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
        if not event.paused:
            event.n += 1
            sleep(event.tick)
            if full_heartbeat and event.n % 3:
                # TODO: every n minutes changes session_key for safety...
                msg_heartbeat = device.generate_msg(msg_com=MsgComExt.HEARTBEAT_FULL, event=event)
            else:
                msg_heartbeat = device.generate_msg(msg_com=MsgComExt.HEARTBEAT, event=event)

            if device.pyqtsignal_connected and device.type is DeviceType.SERVER:
                msg = device.generate_msg(msg_com=MsgComInt.HEARTBEAT, event=event)
                device.signal.emit(msg)

            thinker.add_task_out(msg_heartbeat)


def internal_info_logic(event: ThinkerEvent):
    # TODO: why I need it?
    thinker: Thinker = event.parent
    device = thinker.parent
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    while event.active:
        if not event.paused:
            sleep(event.tick)
            # TODO': requires update
            #msg = MsgGenerator.degen_msg('device_info_short', device, event=event)
            #thinker.add_task_out(msg)


def task_in_reaction(event: ThinkerEvent):
    thinker: Thinker = event.parent
    tasks_in: MsgDict = thinker.tasks_in
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    exclude_msgs = [MsgComExt.HEARTBEAT.msg_name, MsgComExt.HEARTBEAT_FULL.msg_name]
    while event.active:
        if not event.paused and tasks_in:
            try:
                msg: MessageExt = tasks_in.popitem()[1]
                thinker.msg_counter += 1
                react = True
                if msg.com not in exclude_msgs:
                    info_msg(event, 'INFO', extra=str(msg.short()))

                if msg.reply_to == '' and msg.receiver_id != '':  # If message is not a reply, it must be a demand one
                    thinker.add_reply_pending(msg)
                    info_msg(event, 'INFO', f'Expect a reply to {msg.id} com={msg.com}. Adding to pending_reply.')

                elif msg.reply_to != '':
                    if msg.reply_to in thinker.demands_pending_answer:
                        # TODO: should it have else clause or not?
                        com = thinker.demands_pending_answer[msg.reply_to].message.com
                        event.logger.info(f'REPLY to Msg {msg.reply_to} {com} is obtained.')
                        del thinker.demands_pending_answer[msg.reply_to]
                    else:
                        react = False
                        info_msg(event, 'INFO', f'Reply to msg {msg.reply_to} arrived too late.')
                if react:
                    thinker.react_external(msg)
            except (ThinkerErrorReact, Exception) as e:
                error_logger(event, task_in_reaction, f'{e}: {msg}')


def task_out_reaction(event: ThinkerEvent):
    thinker: Thinker = event.parent
    tasks_out: MsgDict = thinker.tasks_out
    tasks_reply_pending: MsgDict = thinker.replies_pending_answer
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    react=False
    while event.active:
        if not event.paused and tasks_out:
            try:
                msg: MessageExt = tasks_out.popitem()[1]
                react = True
                if msg.receiver_id != '' and msg.reply_to == '':
                    # If msg is not reply, than add to pending demand
                    thinker.add_demand_pending(msg)

                elif msg.reply_to != '':
                    if msg.reply_to in tasks_reply_pending:
                        try:
                            com = tasks_reply_pending[msg.reply_to].message.com
                            del tasks_reply_pending[msg.reply_to]
                            event.logger.info(f'Msg id={msg.reply_to} {com} is deleted from tasks_reply_pending')
                        except KeyError as e:
                            event.logger.error(e)
                    else:
                        react = False
                        event.logger.info(f'Timeout for message {msg.short()}')
                if react:
                    thinker.parent.send_msg_externally(msg)
            except (ThinkerErrorReact, Exception) as e:
                error_logger(event, task_out_reaction, f'{e}: {msg}')


def pending_demands(event: ThinkerEvent): 
    thinker: Thinker = event.parent
    tasks_pending_demands: MsgDict = thinker.demands_pending_answer
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    while event.active:
        if not event.paused and tasks_pending_demands:
            try:
                sleep(event.tick)
                for key, item in tasks_pending_demands.items():
                    pending: PendingReply = item
                    if (time() - event.time) > event.tick and pending.attempt < 3:
                        pending.attempt += 1
                        info_msg(event, 'INFO', f'Pending message awaits {pending.attempt}: {pending.message.short()}')
                    elif (time() - event.time) > event.tick and pending.attempt >= 3:
                        try:
                            msg = pending.message
                            del tasks_pending_demands[key]
                            info_msg(event, 'INFO', f'Timeout for demand msg: {msg.short()}')
                            info_msg(event, 'INFO', f'Msg id={msg.id} is deleted')
                        except KeyError:
                            error_logger(event, pending_demands, f'Cannot delete msg id={msg.id} com={msg.com} from '
                                                                 f'pending_demands')
            except ThinkerErrorReact as e:
                error_logger(event, pending_demands, e)


def pending_replies(event: ThinkerEvent):
    thinker: Thinker = event.parent
    device = thinker.parent
    tasks_pending_replies: MsgDict = thinker.replies_pending_answer
    info_msg(event, 'STARTED', extra=f' of {thinker.name} with tick {event.tick}')
    while event.active:
        if not event.paused and tasks_pending_replies:
            sleep(event.tick)
            try:
                for key, item in tasks_pending_replies.items():
                    pending: PendingReply = item
                    if (time() - event.time) > event.tick and pending.attempt < 3:
                        pending.attempt = pending.attempt + 1
                        info_msg(event, 'INFO', f'Pending reply message waits {pending.attempt}: {pending.message}')
                    elif (time() - event.time) > event.tick and pending.attempt >= 3:
                        try:
                            msg = pending.message
                            msg_out = device.generate_msg(msg_com=MsgComExt.ERROR, error_comments='timeout',
                                                          reply_to=msg.id, receiver_id=msg.sender_id)
                            thinker.add_task_out(msg_out)
                            del tasks_pending_replies[key]
                            info_msg(event, 'INFO', f'Timeout for reply msg: {msg.short}')
                            info_msg(event, 'INFO', f'Msg: {msg.id} is deleted')
                        except KeyError:
                            error_logger(event, pending_replies, f'Cannot delete msg: {msg.reply_to} from pending_replies')
            except ThinkerErrorReact as e:
                error_logger(event, pending_replies, e)



def postponed_reaction(replier: Callable[[MessageExt], None], reaction: MessageExt, t: float=1.0, logger=None):
    # TODO: why it is needed in the first place?
    def f():
        if logger:
            logger.info(f'Postponed_reaction for {reaction.short()} started')
        sleep(t)
        replier(reaction)
    trd = Thread(target=f)
    trd.start()
