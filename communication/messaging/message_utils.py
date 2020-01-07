from abc import abstractmethod
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


DEMAND = 'demand'
REPLY = 'reply'
INFO = 'info'
FORWARD = 'forward'
mes_types = [DEMAND, REPLY, INFO]

class MsgGenerator:
    # TODO: return back to without _ style
    _COMMANDS = ['available_services_demand', 'available_services_reply', 'do_it', 'done_it', 'error', 'forward_msg',
                 'heartbeat', 'hello', 'status_server_info', 'status_server_info_full', 'status_server_demand',
                 'status_server_reply', 'status_service', 'info_service_demand', 'info_service_reply',
                 'reply_on_forwarded_demand', 'status_client_info','status_client_demand', 'status_client_reply',
                 'shutdown_info', 'welcome_info']
    AVAILABLE_SERVICES_DEMAND = mes.MessageStructure(DEMAND, None, 'available_services_demand')
    AVAILABLE_SERVICES_REPLY = mes.MessageStructure(REPLY, mes.AvailableServices, 'available_services_reply')
    DO_IT = mes.MessageStructure(DEMAND, mes.DoIt, 'do_it')
    DONE_IT = mes.MessageStructure(REPLY, mes.DoneIt, 'done_it')
    ERROR = mes.MessageStructure(REPLY, mes.Error, 'error')
    FORWARD_MSG = mes.MessageStructure(FORWARD, mes.Forward_msg, 'forward_msg')
    HEARTBEAT = mes.MessageStructure(INFO, mes.EventInfoMes, 'heartbeat')
    HELLO = mes.MessageStructure(DEMAND, mes.DeviceInfoMes, 'hello')
    STATUS_SERVER_INFO = mes.MessageStructure(INFO, mes.ServerStatusMes, 'status_server_info')
    STATUS_SERVER_INFO_FULL = mes.MessageStructure(INFO, mes.ServerStatusExtMes, 'status_server_info_full')
    STATUS_SERVER_DEMAND = mes.MessageStructure(DEMAND, None, 'status_server_demand')
    STATUS_SERVER_REPLY = mes.MessageStructure(REPLY, mes.ServerStatusMes, 'status_server_reply')
    STATUS_SERVICE_INFO = mes.MessageStructure(INFO, mes.ServiceStatusMes, 'status_service_info')
    INFO_SERVICE_DEMAND = mes.MessageStructure(DEMAND, None, 'info_service_demand')
    INFO_SERVICE_REPLY = mes.MessageStructure(REPLY, mes.ServiceInfoMes, 'info_service_reply')
    STATUS_CLIENT_INFO = mes.MessageStructure(INFO, mes.ClientStatusMes, 'status_client_info')
    STATUS_CLIENT_DEMAND = mes.MessageStructure(DEMAND, mes.CheckClient, 'status_client_demand')
    STATUS_CLIENT_REPLY = mes.MessageStructure(REPLY, mes.ClientStatusMes, 'status_client_reply')
    SHUTDOWN_INFO = mes.MessageStructure(INFO, mes.ShutDownMes, 'shutdown_info')
    REPLY_ON_FORWARDED_DEMAND = mes.MessageStructure(REPLY, None, 'reply_on_forwarded_demand')
    WELCOME_INFO = mes.MessageStructure(REPLY, mes.DeviceInfoMes, 'welcome_info')

    @staticmethod
    def available_services_demand(device):
        return MsgGenerator._gen_msg(MsgGenerator.AVAILABLE_SERVICES_DEMAND, device)

    @staticmethod
    def available_services_reply(device, msg_i: mes.Message):
        return MsgGenerator._gen_msg(MsgGenerator.AVAILABLE_SERVICES_REPLY, device=device, msg_i=msg_i)

    @staticmethod
    def do_it(device, com: str, parameters: dict, service_id):
        return MsgGenerator._gen_msg(MsgGenerator.DO_IT, device, com=com, parameters=parameters, rec_id=service_id)

    @staticmethod
    def done_it(device, msg_i: Message, result, comments: str):
        return MsgGenerator._gen_msg(MsgGenerator.DONE_IT, device, msg_i=msg_i, result=result, comments=comments)

    @staticmethod
    def error(device, msg_i: mes.Message, comments="nothing to say about this error..."):
        return MsgGenerator._gen_msg(MsgGenerator.ERROR, device=device, msg_i=msg_i, comments=comments)

    @staticmethod
    def forward_msg(device, msg_i):
        return MsgGenerator._gen_msg(MsgGenerator.FORWARD_MSG, device=device, msg_i=msg_i)

    @staticmethod
    def heartbeat(device, event, n):
        return MsgGenerator._gen_msg(MsgGenerator.HEARTBEAT, device=device, event=event, n=n)

    @staticmethod
    def hello(device):
        return MsgGenerator._gen_msg(MsgGenerator.HELLO, device=device)

    @staticmethod
    def status_server_info(device):
        return MsgGenerator._gen_msg(MsgGenerator.STATUS_SERVER_INFO, device=device)

    @staticmethod
    def status_server_info_full(device):
        return MsgGenerator._gen_msg(MsgGenerator.STATUS_SERVER_INFO_FULL, device=device)

    @staticmethod
    def status_server_demand(device):
        return MsgGenerator._gen_msg(MsgGenerator.STATUS_SERVER_DEMAND, device=device)

    @staticmethod
    def status_server_reply(device, msg_i: mes.Message):
        return MsgGenerator._gen_msg(MsgGenerator.STATUS_SERVER_REPLY, device=device, msg_i=msg_i)

    @staticmethod
    def status_service_info(device):
        return MsgGenerator._gen_msg(MsgGenerator.STATUS_SERVICE_INFO, device=device)

    @staticmethod
    def info_service_demand(device, service_id):
        return MsgGenerator._gen_msg(MsgGenerator.INFO_SERVICE_DEMAND, device=device, rec_id=service_id)

    @staticmethod
    def info_service_reply(device, msg_i: mes.Message):
        return MsgGenerator._gen_msg(MsgGenerator.INFO_SERVICE_REPLY, device=device, msg_i=msg_i)

    @staticmethod
    def reply_on_forwarded_demand(device, msg_i: mes.Message, msg_reply: mes.Message):
        return MsgGenerator._gen_msg(MsgGenerator.REPLY_ON_FORWARDED_DEMAND,
                                     device=device, msg_i=msg_i, msg_reply=msg_reply)

    @staticmethod
    def status_client_info(device):
        return MsgGenerator._gen_msg(MsgGenerator.STATUS_CLIENT_INFO, device=device)

    @staticmethod
    def status_client_demand(device, client_id):
        return MsgGenerator._gen_msg(MsgGenerator.STATUS_CLIENT_DEMAND, device=device, client_id=client_id)

    @staticmethod
    def status_client_reply(device, msg_i: mes.Message):
        return MsgGenerator._gen_msg(MsgGenerator.STATUS_CLIENT_REPLY, device=device, msg_i=msg_i)

    @staticmethod
    def shutdown_info(device, reason='unknown'):
        return MsgGenerator._gen_msg(MsgGenerator.SHUTDOWN_INFO, device=device, reason=reason)

    @staticmethod
    def welcome_info(device, msg_i):
        return MsgGenerator._gen_msg(MsgGenerator.WELCOME_INFO, device=device, msg_i=msg_i)

    @staticmethod
    def _gen_msg(command: mes.MessageStructure, device, **kwargs) -> mes.Message:
        type_com: str = command.type

        if type_com == FORWARD:
            msg_i = kwargs['msg_i']
            return msg_i

        com_name: str = command.mes_name
        mes_info_class: mes.DataClass = command.mes_class
        reply_to = ''

        #  Check if correct device object was passed to the function
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
            module_logger.error(f'IN gen_msg point1 {e}')
            raise e

        if type_com in [DEMAND, INFO]:
            body = mes.MessageBody(type_com, ms_id, rec_id)
        else:
            msg_i: mes.Message = kwargs['msg_i']
            reply_to = msg_i.id
            body = MessageBody(type_com, ms.id, msg_i.body.sender_id)

        #  main logic for functions
        try:
            crypted = True
            if com_name == MsgGenerator.AVAILABLE_SERVICES_DEMAND.mes_name:
                data_info = None
            elif com_name == MsgGenerator.AVAILABLE_SERVICES_REPLY.mes_name:
                data_info = mes_info_class(device.services_running, all_services={})
            elif com_name == MsgGenerator.DO_IT.mes_name:
                body.receiver_id = kwargs['rec_id']
                data_info = mes_info_class(com=kwargs['com'], parameters=kwargs['parameters'])
            elif com_name == MsgGenerator.DONE_IT.mes_name:
                msg_i = kwargs['msg_i']
                com = msg_i.data.info.com
                data_info = mes_info_class(com=com, result=kwargs['result'], comments=kwargs['comments'])
            elif com_name == MsgGenerator.ERROR.mes_name:
                comments: str = kwargs['comments']
                data_info = mes_info_class(comments)
            elif com_name == MsgGenerator.FORWARD_MSG.mes_name:
                pass
            elif com_name == MsgGenerator.HEARTBEAT.mes_name:
                crypted = False
                event = kwargs['event']
                data_info = mes_info_class(event.id,
                                           event.external_name,
                                           device.id,
                                           tick=event.tick,
                                           n=kwargs['n'],
                                           sockets=device.messenger.public_sockets)
            elif com_name == MsgGenerator.HELLO.mes_name:
                data_info = mes_info_class(name=device.name,
                                           device_id=device.id,
                                           messenger_id=device.messenger.id,
                                           type=device.type,
                                           class_type=device.__class__.__name__,
                                           device_status=device.device_status,
                                           public_sockets=device.messenger.public_sockets)
            elif com_name == MsgGenerator.STATUS_SERVER_INFO.mes_name:
                data_info = mes_info_class(device.device_status,
                                           services_running=device.services_running,
                                           services_available=device.services_available)
            elif com_name == MsgGenerator.STATUS_SERVER_INFO_FULL.mes_name:
                if device.thinker:
                    events = device.thinker.events
                else:
                    events = {}
                data_info = mes_info_class(device.device_status,
                                           services_running=device.services_running,
                                           services_available=device.services_available,
                                           events_running=events,
                                           clients_running=device.clients_running)
            elif com_name == MsgGenerator.STATUS_SERVER_DEMAND.mes_name:
                data_info = None
            elif com_name == MsgGenerator.STATUS_SERVER_REPLY.mes_name:
                data_info = mes_info_class(device.device_status,
                                           services_running=device.services_running,
                                           services_available=device.services_available)
            elif com_name == MsgGenerator.STATUS_SERVICE_INFO.mes_name:
                data_info = mes_info_class(device.device_status)
            elif com_name == MsgGenerator.INFO_SERVICE_DEMAND.mes_name:
                body.receiver_id = kwargs['rec_id']
                data_info = None
            elif com_name == MsgGenerator.INFO_SERVICE_REPLY.mes_name:
                data_info = mes_info_class(device.device_status,
                                                   device.id,
                                                   device.description(),
                                                   available_public_functions=device.available_public_functions())
            elif com_name == MsgGenerator.REPLY_ON_FORWARDED_DEMAND.mes_name:
                msg_reply: Message = kwargs['msg_reply']
                data_info = msg_reply.data.info
            elif com_name == MsgGenerator.STATUS_CLIENT_INFO.mes_name:
                data_info = mes_info_class(device.device_status)
            elif com_name == MsgGenerator.STATUS_CLIENT_DEMAND.mes_name:
                data_info = mes_info_class(client_id=kwargs['client_id'])
            elif com_name == MsgGenerator.STATUS_CLIENT_REPLY.mes_name:
                data_info = mes_info_class(device.device_status)
            elif com_name == MsgGenerator.SHUTDOWN_INFO.mes_name:
                data_info = mes_info_class(device.id, reason=kwargs['reason'])
            elif com_name == MsgGenerator.WELCOME_INFO.mes_name:
                data_info = mes_info_class(name=device.name,
                                           device_id=device.id,
                                           messenger_id=device.messenger.id,
                                           type=device.type,
                                           class_type=device.__class__.__name__,
                                           device_status=device.device_status,
                                           public_sockets=device.messenger.public_sockets)
            else:
                raise MsgComNotKnown(com_name)



            msg = mes.Message(body, mes.MessageData(com_name, data_info), reply_to=reply_to, crypted=crypted)

            if not MsgGenerator.msg_verification(msg):
                raise MsgError('Message verification did not pass')
            else:
                return msg

        except (MsgComNotKnown, MsgError, Exception) as e:
            module_logger.error(f'IN gen_msg point 2 {com_name}: {e}')
            raise e

    @staticmethod
    def msg_verification(msg: mes.Message) -> bool:
        try:
            mes_class_var = isinstance(msg, mes.Message)
            mes_type_ver = True if msg.body.type in mes_types else False
            mes_com_ver = True if msg.data.com in MsgGenerator._COMMANDS else False
            classname = msg.data.info.__class__.__name__
            mes_info_class_ver = True if classname in dir(mes) or msg.data.info is None else False
            return mes_class_var and mes_type_ver and mes_com_ver and mes_info_class_ver
        except Exception as e:
            module_logger.error(f'IN msg_verification {e}')
            return False

    @staticmethod
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
