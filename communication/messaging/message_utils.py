from base64 import b64decode
from json import loads
from zlib import decompress
import utilities.data.messaging.messages as mes

import logging
module_logger = logging.getLogger(__name__)


DEMAND = 'demand'
REPLY = 'reply'
INFO = 'info'
FORWARD = 'forward'
mes_types = [DEMAND, REPLY, INFO]

class MsgGenerator:
    _COMMANDS = ('activate_controller', 'available_services_demand',
                 'are_you_alive_demand', 'are_you_alive_reply',
                 'do_it', 'done_it', 'error', 'forward_msg',
                 'heartbeat', 'hello', 'status_server_info', 'status_server_info_full', 'status_server_demand',
                 'status_server_reply', 'status_service', 'info_service_demand', 'info_service_reply',
                 'reply_on_forwarded_demand', 'power_on_demand', 'power_on_reply',
                 'status_client_info','status_client_demand', 'status_client_reply',
                 'shutdown_info', 'welcome_info')
    #ARE_YOU_ALIVE_DEMAND = mes.MessageInfo(DEMAND, mes.AreYouAliveDemand, 'are_you_alive_demand')
    #ARE_YOU_ALIVE_REPLY = mes.MessageInfo(REPLY, None, 'are_you_alive_reply')
    #DO_IT = mes.MessageInfo(DEMAND, mes.DoIt, 'do_it')
    #DONE_IT = mes.MessageInfo(REPLY, mes.DoneIt, 'done_it')
    #HELLO = mes.MessageInfo(DEMAND, mes.WelcomeInfoDevice, 'hello')
    #STATUS_SERVER_INFO = mes.MessageInfo(INFO, mes.ServerStatusMes, 'status_server_info')
    #STATUS_SERVER_INFO_FULL = mes.MessageInfo(INFO, mes.ServerStatusExtMes, 'status_server_info_full')
    #STATUS_SERVER_DEMAND = mes.MessageInfo(DEMAND, None, 'status_server_demand')
    #STATUS_SERVER_REPLY = mes.MessageInfo(REPLY, mes.ServerStatusMes, 'status_server_reply')
    #STATUS_SERVICE_INFO = mes.MessageInfo(INFO, mes.ServiceStatusMes, 'status_service_info')
    #INFO_SERVICE_DEMAND = mes.MessageInfo(DEMAND, None, 'info_service_demand')
    #INFO_SERVICE_REPLY = mes.MessageInfo(REPLY, mes.ServiceInfoMes, 'info_service_reply')
    #POWER_ON_DEMAND = mes.MessageInfo(DEMAND, mes.PowerOnDemand, 'power_on_demand')
    #POWER_ON_REPLY = mes.MessageInfo(REPLY, mes.PowerOnReply, 'power_on_reply')
    #STATUS_CLIENT_INFO = mes.MessageInfo(INFO, mes.ClientStatusMes, 'status_client_info')
    #STATUS_CLIENT_DEMAND = mes.MessageInfo(DEMAND, mes.CheckClient, 'status_client_demand')
    #STATUS_CLIENT_REPLY = mes.MessageInfo(REPLY, mes.ClientStatusMes, 'status_client_reply')


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
        except Exception:  # TODO replace exception by something meaningful
            try:
                mes_dc = loads(decompress(b64decode(msg_json)))
                mes = eval(mes_dc)
                return mes
            except Exception as e:  # TODO replace exception by something meaningful
                module_logger.error(f'IN json_to_message {e} msg_json: {msg_json}, mes_dc: {mes_dc}, mes: {mes}')
                raise
