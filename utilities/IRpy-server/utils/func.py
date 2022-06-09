from json import dumps

def send_byte(self, message_in, json=False):
    if json:
        message_out = dumps(message_in)
    else:
        message_out = str(message_in)
    self.send(bytearray(message_out, 'utf-8'))  # send returned value as bytearry to clien
