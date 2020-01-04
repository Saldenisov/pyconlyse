from base64 import b64decode
from json import loads
from zlib import decompress

import utilities.data.messages as mes
from typing import Union
from communication.interfaces import MessengerInter
from errors.myexceptions import MsgComNotKnown, MsgError
from devices.interfaces import DeviceInter
from utilities.data.messages import *  # This line is required for json_to_message

module_logger = logging.getLogger(__name__)

mes_types = ['demand', 'reply', 'info']

class MsgCommands:
    AVAILABLE_SERVICES = mes.MessageStructure('demand', None),
    AVAILABLE_SERVICES_REPLY = mes.MessageStructure('reply', mes.AvailableServices),
    ERROR_MESSAGE = mes.MessageStructure('reply', mes.Error),

    @classmethod
    def msg_verification(msg: mes.Message) -> bool:
        try:
            mes_class_var = isinstance(msg, mes.Message)
            mes_type_ver = True if msg.body.type in mes_types else False
            mes_com_ver = True if msg.data.com in commands else False
            classname = msg.data.info.__class__.__name__
            mes_info_class_ver = True if classname in dir(mes) or msg.data.info is None else False
            return mes_class_var and mes_type_ver and mes_com_ver and mes_info_class_ver
        except Exception as e:
            module_logger.error(f'IN msg_verification {e}')
            return False

    @classmethod
    def gen_msg(cls, device, **kwargs) -> mes.Message:
        # TODO: crypted option should be added to all commands

        try:
            if com not in commands:
                raise MsgComNotKnown(com)
            else:
                type_com: str = commands[com].type
                reply_to = ''

                try:
                    if isinstance(device, DeviceInter):
                        ms = device.messenger
                        ms_id = ms.id
                        try:
                            rec_id = device.server_msgn_id
                        except AttributeError:
                            try:
                                rec_id = kwargs['rec_id']
                            except KeyError:
                                rec_id = ''
                    elif isinstance(device, MessengerInter):
                        ms = device
                        ms_id = ms.id
                        rec_id = ''
                    else:
                        raise Exception('device is not Device or not Messenger')
                except Exception as e:
                    module_logger.error(e)
                    raise e
                mes_info_class: mes.DataClass = commands[com].mes_class
                try:
                    if type_com != 'reply':
                        body = mes.MessageBody(type_com, ms_id, rec_id)
                    else:
                        msg_i: mes.Message = kwargs['msg_i']
                        body = MessageBody(type_com, ms.id, msg_i.body.sender_id)
                        reply_to = msg_i.id
                except KeyError as e:
                    module_logger.error(e)
                    raise MsgError('msg_i is not present in gen_msg functions')
                except Exception as e:
                    module_logger.error(f'IN gen_msg point1 {e}')
                    raise MsgError(f'Something went so wrong: {e}')

            crypted = True
            if com == 'error_message':
                try:
                    comments: str = kwargs['comments']
                except KeyError:
                    comments = 'Comments were not added. Default comment is None'
                data_info = mes_info_class(comments)
            elif com == 'heartbeat':
                crypted = False
                try:
                    event = kwargs['event']
                except KeyError:
                    event = device.thinker.events['heartbeat']
                data_info = mes_info_class(event.id,
                                           event.external_name,
                                           device.id,
                                           tick=event.tick,
                                           n=kwargs['n'],
                                           sockets=device.messenger.public_sockets)
            elif com == 'hello':
                data_info = mes_info_class(name=device.name,
                                           device_id=device.id,
                                           messenger_id=device.messenger.id,
                                           type=device.type,
                                           class_type=device.__class__.__name__,
                                           device_status=device.device_status,
                                           public_sockets=device.messenger.public_sockets)
            elif com == 'status_server':
                server = device
                data_info = mes_info_class(device.device_status,
                                           services_running=server.services_running,
                                           services_available=server.services_available)
            elif com == 'status_server_full':
                server = device
                if server.thinker:
                    events = server.thinker.events
                else:
                    events = {}
                data_info = mes_info_class(device.device_status,
                                           services_running=server.services_running,
                                           services_available=server.services_available,
                                           events_running=events,
                                           clients_running=server.clients_running
                                           )
            elif com == 'status_server_demand':
                data_info = mes_info_class
            elif com == 'status_server_reply':
                server = device
                data_info = mes_info_class(device.device_status,
                                           services_running=server.services_running,
                                           services_available=server.services_available)
            elif com == 'status_service':
                service = device
                data_info = mes_info_class(service.device_status)
            elif com == 'info_service_demand':
                data_info = mes_info_class(service_id=kwargs['service_id'])
            elif com == 'info_service_reply':
                try:
                    msg_reply = kwargs['msg_reply']
                except KeyError:
                    msg_reply = None
                if not msg_reply:
                    try:
                        data_info = mes_info_class(device.device_status,
                                                   device.id,
                                                   device.description(),
                                                   available_public_functions=device.available_public_functions())
                        print(data_info)
                    except AttributeError:
                        raise
                else:
                    data_info = msg_reply.data.info
            elif com == 'status_client':
                client = device
                data_info = mes_info_class(client.device_status)
            elif com == 'status_client_demand':
                data_info = mes_info_class(client_id=kwargs['client_id'])
            elif com == 'status_client_reply':
                client = device
                data_info = mes_info_class(client.device_status)
            elif com == 'shutdown':
                try:
                    reason = kwargs['reason']
                except KeyError:
                    reason = 'unknown'
                data_info = mes_info_class(device.id, reason=reason)
            elif com == 'reply_on_forwarded_demand':
                try:
                    msg_reply: Message = kwargs['msg_reply']
                except KeyError:
                    raise Exception(f'msg_reply was not passed to com: {com}')
                data_info = msg_reply.data.info
            elif com == 'welcome':
                data_info = mes_info_class(name=device.name,
                                           device_id=device.id,
                                           messenger_id=device.messenger.id,
                                           type=device.type,
                                           class_type=device.__class__.__name__,
                                           device_status=device.device_status,
                                           public_sockets=device.messenger.public_sockets)
            elif com == 'available_services':
                data_info = None
            elif com == 'available_services_reply':
                data_info = mes_info_class(device.services_running, all_services={})
            elif com == 'unknown_message':
                data_info = mes_info_class(comment='Command is not known to thinker')
            elif com == 'test':
                data_info = mes_info_class()
            else:
                raise MsgComNotKnown(com)

            msg = mes.Message(body, mes.MessageData(com, data_info), reply_to=reply_to, crypted=crypted)

            if not msg_verification(msg):
                raise MsgError('Message verification did not pass')
            else:
                return msg
        except (MsgComNotKnown, MsgError, Exception) as e:
            module_logger.error(f'IN gen_msg point 2 {com}: {e}')
            raise e

    @classmethod
    def json_to_message(msg_json: str) -> mes.Message:
        mes_dc = None
        mes = None
        try:
            mes_str = loads(msg_json)
            return eval(mes_str)
        except Exception:
            try:
                mes_dc = loads(decompress(b64decode(msg_json)))
                mes = eval(mes_dc)
                return mes
            except Exception as e:
                module_logger.error(f'IN json_to_message {e} msg_jso: {msg_json}, mes_dc: {mes_dc}, mes: {mes}')
                raise

MsgCommands.gen_msg(MsgCommands.AVAILABLE_SERVICES)


commands = {'available_services': mes.MessageStructure('demand', None),
    'available_services_reply': mes.MessageStructure('reply', mes.AvailableServices),
    'error_message': mes.MessageStructure('reply', mes.Error),
    'forward': mes.MessageStructure('reply', mes.Error),
    'heartbeat': mes.MessageStructure('info', mes.EventInfoMes),
    'hello': mes.MessageStructure('demand', mes.DeviceInfoMes),
    'status_server': mes.MessageStructure('info', mes.ServerStatusMes),
    'status_server_full': mes.MessageStructure('info', mes.ServerStatusExtMes),
    'status_server_demand': mes.MessageStructure('demand', None),
    'status_server_reply': mes.MessageStructure('reply', mes.ServerStatusMes),
    'status_service': mes.MessageStructure('info', mes.ServiceStatusMes),
    'info_service_demand': mes.MessageStructure('demand', mes.CheckService),
    'info_service_reply': mes.MessageStructure('reply', mes.ServiceInfoMes),
    'status_client': mes.MessageStructure('info', mes.ClientStatusMes),
    'status_client_demand': mes.MessageStructure('demand', mes.CheckClient),
    'status_client_reply': mes.MessageStructure('reply', mes.ClientStatusMes),
    'shutdown': mes.MessageStructure('info', mes.ShutDownMes),
    'reply_on_forwarded_demand': mes.MessageStructure('reply', None),
    'unknown_message': mes.MessageStructure('info', mes.Unknown),
    'welcome': mes.MessageStructure('reply', mes.DeviceInfoMes),
    'test': mes.MessageStructure('info', mes.Test)}


def msg_verification(msg: mes.Message) -> bool:
    try:
        mes_class_var = isinstance(msg, mes.Message)
        mes_type_ver = True if msg.body.type in mes_types else False
        mes_com_ver = True if msg.data.com in commands else False
        classname = msg.data.info.__class__.__name__
        mes_info_class_ver = True if classname in dir(mes) or msg.data.info is None else False
        return mes_class_var and mes_type_ver and mes_com_ver and mes_info_class_ver
    except Exception as e:
        module_logger.error(f'IN msg_verification {e}')
        return False


def gen_msg(com: str, device, **kwargs) -> mes.Message:
    # TODO: crypted option should be added to all commands

    try:
        if com not in commands:
            raise MsgComNotKnown(com)
        else:
            type_com: str = commands[com].type
            reply_to = ''

            try:
                if isinstance(device, DeviceInter):
                    ms = device.messenger
                    ms_id = ms.id
                    try:
                        rec_id = device.server_msgn_id
                    except AttributeError:
                        try:
                            rec_id = kwargs['rec_id']
                        except KeyError:
                            rec_id = ''
                elif isinstance(device, MessengerInter):
                    ms = device
                    ms_id = ms.id
                    rec_id = ''
                else:
                    raise Exception('device is not Device or not Messenger')
            except Exception as e:
                module_logger.error(e)
                raise e
            mes_info_class: mes.DataClass = commands[com].mes_class
            try:
                if type_com != 'reply':
                    body = mes.MessageBody(type_com, ms_id, rec_id)
                else:
                    msg_i: mes.Message = kwargs['msg_i']
                    body = MessageBody(type_com, ms.id, msg_i.body.sender_id)
                    reply_to = msg_i.id
            except KeyError as e:
                module_logger.error(e)
                raise MsgError('msg_i is not present in gen_msg functions')
            except Exception as e:
                module_logger.error(f'IN gen_msg point1 {e}')
                raise MsgError(f'Something went so wrong: {e}')

        crypted = True
        if com == 'error_message':
            try:
                comments: str = kwargs['comments']
            except KeyError:
                comments = 'Comments were not added. Default comment is None'
            data_info = mes_info_class(comments)
        elif com == 'heartbeat':
            crypted = False
            try:
                event = kwargs['event']
            except KeyError:
                event = device.thinker.events['heartbeat']
            data_info = mes_info_class(event.id,
                                       event.external_name,
                                       device.id,
                                       tick=event.tick,
                                       n=kwargs['n'],
                                       sockets=device.messenger.public_sockets)
        elif com == 'hello':
            data_info = mes_info_class(name=device.name,
                                       device_id=device.id,
                                       messenger_id=device.messenger.id,
                                       type=device.type,
                                       class_type=device.__class__.__name__,
                                       device_status=device.device_status,
                                       public_sockets=device.messenger.public_sockets)
        elif com == 'status_server':
            server = device
            data_info = mes_info_class(device.device_status,
                                       services_running=server.services_running,
                                       services_available=server.services_available)
        elif com == 'status_server_full':
            server = device
            if server.thinker:
                events = server.thinker.events
            else:
                events = {}
            data_info = mes_info_class(device.device_status,
                                       services_running=server.services_running,
                                       services_available=server.services_available,
                                       events_running=events,
                                       clients_running=server.clients_running
                                       )
        elif com == 'status_server_demand':
            data_info = mes_info_class
        elif com == 'status_server_reply':
            server = device
            data_info = mes_info_class(device.device_status,
                                       services_running=server.services_running,
                                       services_available=server.services_available)
        elif com == 'status_service':
            service = device
            data_info = mes_info_class(service.device_status)
        elif com == 'info_service_demand':
            data_info = mes_info_class(service_id=kwargs['service_id'])
        elif com == 'info_service_reply':
            try:
                msg_reply = kwargs['msg_reply']
            except KeyError:
                msg_reply = None
            if not msg_reply:
                try:
                    data_info = mes_info_class(device.device_status,
                                               device.id,
                                               device.description(),
                                               available_public_functions=device.available_public_functions())
                    print(data_info)
                except AttributeError:
                    raise
            else:
                data_info = msg_reply.data.info
        elif com == 'status_client':
            client = device
            data_info = mes_info_class(client.device_status)
        elif com == 'status_client_demand':
            data_info = mes_info_class(client_id=kwargs['client_id'])
        elif com == 'status_client_reply':
            client = device
            data_info = mes_info_class(client.device_status)
        elif com == 'shutdown':
            try:
                reason = kwargs['reason']
            except KeyError:
                reason = 'unknown'
            data_info = mes_info_class(device.id, reason=reason)
        elif com == 'reply_on_forwarded_demand':
            try:
                msg_reply: Message = kwargs['msg_reply']
            except KeyError:
                raise Exception(f'msg_reply was not passed to com: {com}')
            data_info = msg_reply.data.info
        elif com == 'welcome':
            data_info = mes_info_class(name=device.name,
                                       device_id=device.id,
                                       messenger_id=device.messenger.id,
                                       type=device.type,
                                       class_type=device.__class__.__name__,
                                       device_status=device.device_status,
                                       public_sockets=device.messenger.public_sockets)
        elif com == 'available_services':
            data_info = None
        elif com == 'available_services_reply':
            data_info = mes_info_class(device.services_running, all_services={})
        elif com == 'unknown_message':
            data_info = mes_info_class(comment='Command is not known to thinker')
        elif com == 'test':
            data_info = mes_info_class()
        else:
            raise MsgComNotKnown(com)

        msg = mes.Message(body, mes.MessageData(com, data_info), reply_to=reply_to, crypted=crypted)

        if not msg_verification(msg):
            raise MsgError('Message verification did not pass')
        else:
            return msg
    except (MsgComNotKnown, MsgError, Exception) as e:
        module_logger.error(f'IN gen_msg point 2 {com}: {e}')
        raise e


def json_to_message(msg_json: str) -> mes.Message:
    mes_dc = None
    mes = None
    try:
        mes_str = loads(msg_json)
        return eval(mes_str)
    except Exception:
        try:
            mes_dc = loads(decompress(b64decode(msg_json)))
            mes = eval(mes_dc)
            return mes
        except Exception as e:
            module_logger.error(f'IN json_to_message {e} msg_jso: {msg_json}, mes_dc: {mes_dc}, mes: {mes}')
            raise
