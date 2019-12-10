import zmq
from threading import Thread
import time

def server_init(port=6666):
    context = zmq.Context()
    socket = context.socket(zmq.PAIR)
    socket.bind("tcp://127.0.0.1:%s" % port)
    print('Server init ' + str(port))
    return socket

def client_init(port=6666):
    context = zmq.Context()
    socket = context.socket(zmq.PAIR)
    socket.connect("tcp://127.0.0.1:%s" % port)
    socket.get
    print('Client init ' + str(port))
    return socket


def main_client(clients):
    def read_message(client):
        while True:
            print(client.recv())

    def send_message(client, id):
        while True:
            time.sleep(1)
            client.sendREQ(bytearray('Hello from ' + str(id), 'utf-8'))
    threads =[]
    i = 1
    for client in clients:
        threads.append(Thread(target=read_message,args=[client]))
        threads.append(Thread(target=send_message, args=[client, i]))
        i += 1

    for thread in threads:
        thread.start()



def main_server(server):
    while True:
        message = server.recv()
        print(message)
        server.sendREQ(bytearray("Greatings from server_p", 'utf-8'))
        time.sleep(1)
        server.sendREQ(bytearray("Sleeping", 'utf-8'))

if __name__ == '__main__':
    server = server_init()
    client1 = client_init(6666)
    client2 = client_init(6666)
    thread_server = Thread(target=main_server, args=[server])
    thread_client = Thread(target=main_client, args=[[client1, client2]])

    thread_server.start()
    thread_client.start()
