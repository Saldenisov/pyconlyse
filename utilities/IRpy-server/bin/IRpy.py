import zmq

from os.path import normpath
from types import MethodType

from detectors import IRdet, Avantesdet
from utils import send_byte


DET_CONFIG = {
    'type': 'IRdet',
    'host': "tcp://127.0.0.1:5555",
    'IRdet_DLL': r"C:\Users\Schmidhammer\Desktop\IRpy-server\ESLSCDLL.dll",
    'Avantesdet_DLL': r"C:\Users\Schmidhammer\Desktop\IRpy-server\avantes.dll"
}

def init_settings(DET_CONFIG):
    if DET_CONFIG['type'] == 'IRdet':
        det = IRdet(dllpath=normpath(DET_CONFIG['IRDet_dll']), dev=False)
    elif DET_CONFIG['type'] == 'Avantesdet':
        det = Avantesdet(dllpath=normpath(DET_CONFIG['Avantesdet_dll']), dev=False)
    return  det

def init_zmq(DET_CONFIG):
    context = zmq.Context()
    socket = context.socket(zmq.REP)  # ARCHETYPE for a Smart Messaging
    socket.send_byte = MethodType(socket, send_byte())
    socket.bind(DET_CONFIG['host'])  # PORT ready for LabView to .connect()
    return socket

def main(socket, det):
    while True:
        message = socket.recv()
        print("Received request: %s" % message)
        try:
            if message == "Connect":
                if det.connect():
                    socket.send_byte('Connected')
                else:
                    socket.send_byte('Not connected')

            if message == "Disconnect":
                if det.disconnect():
                    socket.send_byte('Disconnected')
                else:
                    socket.send_byte('Not disconnected')

            if message == 'Stop':
                if det.disconnect():
                    socket.send_byte('Disconnected')
                    exit()
                else:
                    socket.send_byte('Not disconnected')

            if message == 'Readraw':
                pass

        except NameError:
            socket.send_byte( b"Unknown command" )

        except:
            socket.send_byte( b"Unknown error" )


if __name__ == "__main__":
    det = init_settings()
    main(init_zmq(), det)

