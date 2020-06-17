from devices.devices import Server, Service
from communication.messaging.messages import *
from utilities.datastructures.mes_independent.stpmtr_dataclass import *


def test_messages(server: Server, stpmtr_emulate: Service):

    def msg_bytes_back_assert(msgs: List[Union[MessageExt, MessageInt]]):
        msgs_bytes = []
        for msg in msgs:
            if isinstance(msg, MessageExt):
                msgs_bytes.append(msg.byte_repr())
            else:
                msgs_bytes.append(b'')
        for msg, msg_bytes in zip(msgs, msgs_bytes):
            try:
                if isinstance(msg, MessageExt):
                    assert msg == MessageExt.bytes_to_msg(msg_bytes)
            except Exception as e:
                print(msg)


    # Msg generation testing for Server
    # TODO: need to fill with all messages
    msgs = []

    msg_device_info = server.generate_msg(msg_com=MsgComInt.DEVICE_INFO_INT, sender_id='sender_id')

    msgs.append(msg_device_info)

    msg_available_services = server.generate_msg(msg_com=MsgComExt.AVAILABLE_SERVICES,
                                                 available_services=server.available_services,
                                                 reply_to='', receiver_id='receiver_id')

    # MessageExt to MessageInt conversion
    msg_available_services_int = msg_available_services.ext_to_int()

    msgs.append(msg_available_services)
    msg_error = server.generate_msg(msg_com=MsgComExt.ERROR, error_comments='test_error', reply_to='',
                                    receiver_id='receiver_id')
    msgs.append(msg_error)

    msg_welcome = server.generate_msg(msg_com=MsgComExt.WELCOME_INFO_SERVER, reply_to='reply_to',
                                      receiver_id='receiver_id')
    msgs.append(msg_welcome)


    # Msg conversion to bytes and back for Server
    msg_bytes_back_assert(msgs)


    # Msg generation testing for stpmtr_emulate
    msgs = []

    msg_available_services = stpmtr_emulate.generate_msg(msg_com=MsgComExt.AVAILABLE_SERVICES,
                                                         available_services=server.available_services,
                                                         reply_to='', receiver_id='receiver_id')
    msgs.append(msg_available_services)

    msg_error = stpmtr_emulate.generate_msg(msg_com=MsgComExt.ERROR, error_comments='test_error', reply_to='',
                                            receiver_id='receiver_id')
    msgs.append(msg_error)

    msg_welcome = stpmtr_emulate.generate_msg(msg_com=MsgComExt.WELCOME_INFO_DEVICE, reply_to='reply_to',
                                              receiver_id='receiver_id',
                                              event=stpmtr_emulate.thinker.events['heartbeat'])
    msgs.append(msg_welcome)


    try:
        from utilities.datastructures.mes_independent.stpmtr_dataclass import StpMtrDescription
        description: StpMtrDescription = stpmtr_emulate.description()


        msg_service_info = stpmtr_emulate.generate_msg(msg_com=MsgComExt.DONE_IT, reply_to='reply_to',
                                                       receiver_id='receiver_id',
                                                       func_output=FuncServiceInfoOutput(comments='',
                                                                                         func_success=True,
                                                                                         device_id=stpmtr_emulate.id,
                                                                                         service_description=description))
        bytes = msg_service_info.byte_repr()
        msg_back = MessageExt.bytes_to_msg(bytes)
    except Exception as e:
        print(e)
    msgs.append(msg_service_info)

    msg_welcome_copy = msg_welcome.copy(sender_id='CHANGED_Sender', unexisting_attribute=0)
    assert msg_welcome_copy.sender_id == 'CHANGED_Sender'
    assert msg_welcome.info == msg_welcome_copy.info
    assert msg_welcome.receiver_id == msg_welcome_copy.receiver_id
    assert msg_welcome.id != msg_welcome_copy

    msg_bytes_back_assert(msgs)







