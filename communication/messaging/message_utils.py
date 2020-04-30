from communication.messaging.messages import MessageExt

import logging
module_logger = logging.getLogger(__name__)



class MsgGenerator:
    _COMMANDS = ('activate_controller', 'available_services_demand',
                 'are_you_alive_demand', 'are_you_alive_reply',
                 'do_it', 'done_it', 'error', 'forward_msg',
                 'heartbeat', 'hello', 'status_server_info', 'status_server_info_full', 'status_server_demand',
                 'status_server_reply', 'status_service', 'info_service_demand', 'info_service_reply',
                 'reply_on_forwarded_demand', 'power_on_demand', 'power_on_reply',
                 'status_client_info','status_client_demand', 'status_client_reply',
                 'shutdown_info', 'welcome_info')
    #ARE_YOU_ALIVE_DEMAND = mes.MessageInfoExt(DEMAND, mes.AreYouAliveDemand, 'are_you_alive_demand')
    #ARE_YOU_ALIVE_REPLY = mes.MessageInfoExt(REPLY, None, 'are_you_alive_reply')
    #DO_IT = mes.MessageInfoExt(DEMAND, mes.DoIt, 'do_it')
    #DONE_IT = mes.MessageInfoExt(REPLY, mes.DoneIt, 'done_it')
    #HELLO = mes.MessageInfoExt(DEMAND, mes.WelcomeInfoDevice, 'hello')
    #STATUS_SERVER_INFO = mes.MessageInfoExt(INFO, mes.ServerStatusMes, 'status_server_info')
    #STATUS_SERVER_INFO_FULL = mes.MessageInfoExt(INFO, mes.ServerStatusExtMes, 'status_server_info_full')
    #STATUS_SERVER_DEMAND = mes.MessageInfoExt(DEMAND, None, 'status_server_demand')
    #STATUS_SERVER_REPLY = mes.MessageInfoExt(REPLY, mes.ServerStatusMes, 'status_server_reply')
    #STATUS_SERVICE_INFO = mes.MessageInfoExt(INFO, mes.ServiceStatusMes, 'status_service_info')
    #INFO_SERVICE_DEMAND = mes.MessageInfoExt(DEMAND, None, 'info_service_demand')
    #INFO_SERVICE_REPLY = mes.MessageInfoExt(REPLY, mes.ServiceInfoMes, 'info_service_reply')
    #POWER_ON_DEMAND = mes.MessageInfoExt(DEMAND, mes.PowerOnDemand, 'power_on_demand')
    #POWER_ON_REPLY = mes.MessageInfoExt(REPLY, mes.PowerOnReply, 'power_on_reply')
    #STATUS_CLIENT_INFO = mes.MessageInfoExt(INFO, mes.ClientStatusMes, 'status_client_info')
    #STATUS_CLIENT_DEMAND = mes.MessageInfoExt(DEMAND, mes.CheckClient, 'status_client_demand')
    #STATUS_CLIENT_REPLY = mes.MessageInfoExt(REPLY, mes.ClientStatusMes, 'status_client_reply')

def msg_verification(msg: MessageExt) -> bool:
    # TODO: !!!REALIZE!!!
    return True
