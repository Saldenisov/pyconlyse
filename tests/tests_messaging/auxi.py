msg_str = """MessageExt(body=MessageBodyE(message_type='demand', sender='DLClient:DL_emulate:5b8c79fd1ee3b7dd720e583254b7000c', receiver='Server'), data=MessageDataE(com='hello_server', sender_name='ClientMessenger:DLClient:DL_emulate', class_info='HelloServer', info=HelloServer(name='DL_emulate', device_id='DL_emulate:91f1a5b7928ac52a31aa488274040d07', messenger_id='DLClient:DL_emulate:5b8c79fd1ee3b7dd720e583254b7000c', on=True, active=True, public_key='public_key:-)_ClientMessenger:DLClient:DL_emulate', address_publisher=''), reply_to=''), id='e8c85c2875cd5c8733fd9380da4a14e0')"""


print(msg_str.find(', id='))
a= msg_str.find(', id=')
print(msg_str[:msg_str.find(', id=')])

