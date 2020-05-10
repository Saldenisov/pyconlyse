import base64
import logging
import zmq
from abc import abstractmethod
from enum import Enum
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from time import sleep
from typing import Dict, List, NamedTuple, NewType

from communication.interfaces import MessengerInter
from communication.messaging.messages import MessageExt, MsgType, MsgComExt
from datastructures.mes_independent.devices_dataclass import *
from devices.interfaces import DeviceId, DeviceType
from devices.devices import Device
from datastructures.mes_dependent.dicts import MsgDict
from utilities.errors.messaging_errors import MessengerError, MessageError
from utilities.errors.myexceptions import WrongAddress, ThinkerError
from utilities.myfunc import unique_id, info_msg, error_logger, get_local_ip, get_free_port
from utilities.tools.decorators import make_loop


module_logger = logging.getLogger(__name__)

UserSocket = NewType('UserSocketName', str)
FRONTEND_Server = UserSocket('frontend_router_socket_server')
BACKEND_Server = UserSocket('backend_router_socket_server')
DEALER_Socket = UserSocket('dealer_socket')
PUB_Socket = UserSocket('publisher_socket')
PUB_Socket_Server = UserSocket('publisher_socket_server')
SUB_Socket = UserSocket('subscriber_socket')


class MsgTuple(NamedTuple):
    msg: MessageExt
    device_id: DeviceId
    socket_name: UserSocket
    crypted: bool


class Messenger(MessengerInter):

    n_instance = 0

    def __init__(self, name: str, addresses: Dict[str, str], parent: Device, pub_option: bool, **kwargs):
        """

        :param name: user-friendly name
        :param addresses:
        :param parent: Device, messenger can function without parent_logger Device as well
        :param pub_option: tell weather there is a publisher socket
        :param kwargs:
        """

        super().__init__()
        self._attempts_to_restart_sub = 1  # restart subscriber
        self._are_you_alive_send = False
        Messenger.n_instance += 1
        self.logger = logging.getLogger(f'{__name__}.{self.__class__.__name__}')
        self.name = f'{self.__class__.__name__}:{Messenger.n_instance}:{name}:{get_local_ip()}'
        self.id: DeviceId = parent.id
        self.parent: Device = parent
        try:
            self._polling_time = int(self.parent.get_general_settings()['polling']) / 1000.
        except AttributeError:
            self._polling_time = 1
        self.active = False
        self.paused = True
        self._msg_out = MsgDict(name=f'msg_out:{self.id}', size_limit=1000, dict_parent=self)
        # ZMQ sockets, communication info
        self.sockets = {}
        self.public_sockets = {}
        self.addresses = {}
        self.pub_option = pub_option
        self._gen_rsa_keys()


        try:
            info_msg(self, 'INITIALIZING')
            self._verify_addresses(addresses)
            self._create_sockets()
            info_msg(self, 'INITIALIZED')
        except (WrongAddress, zmq.ZMQError) as e:
            info_msg(self, 'NOT INITIALIZED')
            raise MessengerError(str(e))

    def add_msg_out(self, msg: MessageExt):
        try:
            self._msg_out[msg.id] = msg
        except KeyError as e:
            error_logger(self, self.add_msg_out, e)

    @abstractmethod
    def _create_sockets(self):
        pass

    def create_fernet(self, session_key: bytes):
        return Fernet(session_key)

    def decrypt_with_private(self, cipher_text: bytes) -> str:
        """
        Decrypt the cipher text using private key (RSA)
        :param cipher_text: cipher text in bytes
        :return: plain text string
        """
        plaintext = self._private_key.decrypt(cipher_text, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()),
                                                                        algorithm=hashes.SHA1(), label=None))
        return plaintext

    def decrypt_with_session_key(self, msg_bytes: bytes, device_id: DeviceId = None) -> str:
        # TODO: add functionality to messenger.decrypt() when TLS is realized
        try:
            return Fernet(self.parent.connections[device_id].session_key).decrypt(msg_bytes)
        except KeyError:
            raise MessengerError(f'DeviceID is not known, cannot decrypt msg')

    @abstractmethod
    def _deal_with_reaceived_msg(self, msgs: List[MsgTuple]):
        pass

    def encrypt_with_public(self, msg_b: bytes, pem: bytes) -> bytes:
        public_key = self._load_public_key(pem)
        msg_encrypted = public_key.encrypt(msg_b, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()),
                                                                                algorithm=hashes.SHA1(), label=None))
        return msg_encrypted

    def encrypt_with_session_key(self, msg: MessageExt) -> bytes:
        # TODO: add functionality to messenger.encrypt() when TLS is realized
        if msg.crypted:
            try:
                if self.parent.type is DeviceType.SERVER:
                    receiver_id: DeviceId = msg.receiver_id
                else:
                    receiver_id = self.parent.server_id
                return Fernet(self.parent.connections[receiver_id].session_key).encrypt(msg.msgpack_repr())
            except KeyError:
                raise MessengerError(f'DeviceID is not known, cannot encrypt msg')
        else:
            return msg.msgpack_repr()

    def _gen_rsa_keys(self):
        """
        Private and Public Keys are generated with default_backend
        :return: None
        """
        if self.parent.type is DeviceType.SERVER:
            key_size = 4096
        else:
            key_size = 2048
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size, backend=default_backend())
        self._public_key = self._private_key.public_key()


    @abstractmethod
    def info(self):
        from collections import OrderedDict as od
        info = od()
        info['id'] = self.id
        info['status'] = {'active': self.active, 'paused': self.paused}
        info['msg_out'] = self._msg_out
        info['polling_time'] = self._polling_time
        return info

    def _load_public_key(self, pem=b''):
        return load_pem_public_key(pem, default_backend())

    def _load_private_key(self, pem=b''):
        return load_pem_private_key(pem, None, default_backend())

    @abstractmethod
    def info(self):
        from collections import OrderedDict as od
        info = od()
        info['id'] = self.id
        info['status'] = {'active': self.active, 'paused': self.paused}
        info['msg_out'] = self._msg_out
        info['polling_time'] = self._polling_time
        return info

    @property
    def public_key(self):
        return self._public_key.public_bytes(encoding=serialization.Encoding.PEM,
                                             format=serialization.PublicFormat.SubjectPublicKeyInfo)

    def pause(self):
        "put executation of thread on pause"
        self.paused = True
        self.parent.device_status.messaging_paused = self.paused
        self.logger.info(f'{self.name} is paused')
        sleep(0.01)

    @abstractmethod
    def run(self):
        info_msg(self, 'STARTING')
        self.active = True
        self.paused = False
        self.parent.device_status.messaging_on = self.active
        self.parent.device_status.messaging_paused = self.paused
        # Start send loop here
        self._send_loop_logic(await_time=0.1 / 1000.)

    @abstractmethod
    def _receive_msgs(self):
        pass

    def restart_socket(self, socket_name: str, connect_to: str):
        #TODO: realize other sockets
        self.logger.info(f'restarting {socket_name} socket')
        self.pause()
        sock = self.sockets[socket_name]
        self.poller.unregister(sock)
        if socket_name == 'sub':
            sock = self.context.socket(zmq.SUB)
            self.poller.register(sock, zmq.POLLIN)
            self.sockets['sub'] = sock
            self.subscribe_sub(connect_to)
            self.logger.info(f'socket {socket_name} is restarted')
        else:
            pass

        self.unpause()

    @abstractmethod
    def send_msg(self, msg: MessageExt):
        pass

    @make_loop
    def _send_loop_logic(self, await_time):
        if self._msg_out:
            msg: MessageExt = self._msg_out.popitem(last=False)[1]
            self.send_msg(msg)

    def stop(self):
        info_msg(self, 'STOPPING')
        self.active = False
        self.paused = True
        self.parent.device_status.messaging_on = self.active
        self.parent.device_status.messaging_paused = self.paused
        self._msg_out.clear()

    def subscribe_sub(self, address=None, filter_opt=b""):
        try:
            self.sockets[SUB_Socket].connect(address)
            self.sockets[SUB_Socket].setsockopt(zmq.SUBSCRIBE, filter_opt)
            self.sockets[SUB_Socket].setsockopt(zmq.RCVHWM, 3)
            self.logger.info(f'socket sub is connected to {address}')
        except (zmq.ZMQError, Exception) as e:
            error_logger(self, self.subscribe_sub, e)

    @abstractmethod
    def _verify_addresses(self, addresses: Dict[str, str]):
        pass

    def unpause(self):
        """
        depauses execution of sending thread
        :return: None
        """
        self.paused = False
        self.logger.info(f'{self.name} is unpaused')


class ClientMessenger(Messenger):

    socket_names = set([DEALER_Socket, SUB_Socket])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.pub_option:
            self.socket_names.add(PUB_Socket)

    def _create_sockets(self):
        try:
            self.context = zmq.Context()
            # SOCKET DEALER
            dealer = self.context.socket(zmq.DEALER)
            dealer.setsockopt_unicode(zmq.IDENTITY, self.id)
            # SOCKET SUBSCRIBER
            subscriber = self.context.socket(zmq.SUB)
            subscriber.setsockopt(zmq.RCVHWM, 10)

            self.sockets = {DEALER_Socket: dealer, SUB_Socket: subscriber}

            # SOCKET PUBLISHER
            if self.pub_option:
                publisher = self.context.socket(zmq.PUB)
                publisher.setsockopt_unicode(zmq.IDENTITY, self.addresses[PUB_Socket])
                self.sockets[PUB_Socket] = publisher
                self.public_sockets = {PUB_Socket: self.addresses[PUB_Socket]}

            # POLLER
            self.poller = zmq.Poller()
            self.poller.register(dealer, zmq.POLLIN)
            self.poller.register(subscriber, zmq.POLLIN)
        except (WrongAddress, KeyError, zmq.ZMQError) as e:
            error_logger(self, self._create_sockets, e)
            raise e

    def connect(self):
        try:
            self.sockets[DEALER_Socket].connect(self.addresses[FRONTEND_Server])
            if self.pub_option:
                self.bind_pub()
        except (WrongAddress, zmq.error.ZMQBindError) as e:
            error_logger(self, self.connect, e)

    def bind_pub(self):
        try:
            self.sockets[PUB_Socket].setsockopt_unicode(zmq.IDENTITY, self.addresses[PUB_Socket])
            self.sockets[PUB_Socket].bind(self.addresses[PUB_Socket])
        except (WrongAddress, zmq.error.ZMQError) as e:
            # TODO: potential recursion depth violation
            error_logger(self, self.connect, f'{e}: {self.addresses[PUB_Socket]}')
            port = get_free_port(scope=None)
            local_ip = get_local_ip()
            self.addresses[PUB_Socket] = f'tcp://{local_ip}:{port}'
            self.public_sockets = {PUB_Socket: self.addresses[PUB_Socket]}
            self.bind_pub()

    def _deal_with_reaceived_msg(self, msgs: List[MsgTuple]):
        for msg, device_id, socket, crypted in msgs:
            try:
                if int(crypted):
                    device_id = self.parent.server_id  #  !!! ONLY WHEN CLIET/SERVICE HAS DEALER SOCKET
                    msg = self.decrypt_with_session_key(msg, device_id)
                mes: MessageExt = MessageExt.msgpack_bytes_to_msg(msg)
                self.parent.thinker.add_task_in(mes)
            except (MessengerError, MessageError, ThinkerError) as e:
                error_logger(self, self.run, e)
                msg_r = self.parent.generate_msg(msg_com=MsgComExt.ERROR, error_comments=str(e), reply_to='',
                                                 receiver_id=device_id)
                self.add_msg_out(msg_r)

    def info(self):
        return super().info()

    def _receive_msgs(self):
        msgs = []
        while self.active:
            try:
                if not self.paused:
                    sockets = dict(self.poller.poll(1))
                    if self.sockets[DEALER_Socket] in sockets:
                        msg, crypted = self.sockets[DEALER_Socket].recv_multipart()
                        msgs.append(MsgTuple(msg, None, DEALER_Socket, crypted))
                    if self.sockets[SUB_Socket] in sockets:
                        msg, crypted = self.sockets[SUB_Socket].recv_multipart()
                        msgs.append(MsgTuple(msg, None, SUB_Socket, crypted))
                    if msgs:
                        self._deal_with_reaceived_msg(msgs)
                        msgs = []
            except ValueError as e:  # TODO when recv_multipart works wrong! what will happen?
                self.logger.error(e)

    def run(self):
        super().run()
        try:
            for adr in self.addresses[PUB_Socket_Server]:
                self.subscribe_sub(address=adr)
            msg = self._wait_server_hb()
            if self.active:
                self.connect()
                self.parent.thinker.react_heartbeat_full(msg)
                info_msg(self, 'STARTED')
                self._receive_msgs()
        except (zmq.error.ZMQError, MessengerError) as e:  # Bad type of error
            error_logger(self, self.run, e)
            self.stop()
        finally:
            self.sockets[DEALER_Socket].close()
            if self.sockets[SUB_Socket]:
                self.sockets[SUB_Socket].close()
            if self.sockets[PUB_Socket]:
                self.sockets[PUB_Socket].close()
            self.context.destroy()
            self.active = False
            self.paused = True
            info_msg(self, 'STOPPED')

    def send_msg(self, msg: MessageExt):
        try:
            crypted = str(int(msg.crypted)).encode('utf-8')
            msg_bytes = self.encrypt_with_session_key(msg)

            if msg.receiver_id != '':
                self.sockets[DEALER_Socket].send_multipart([msg_bytes, crypted])
                info_msg(self, 'INFO', f'Msg {msg.id}, msg_com {msg.com} is send to {msg.receiver_id}.')
            else:
                if self.pub_option:
                    self.sockets[PUB_Socket].send_multipart([msg_bytes, crypted])
                else:
                    info_msg(self, 'INFO', f'Publisher socket is not available for {self.name}.')
        except zmq.ZMQError as e:
            error_logger(self, self.send_msg, e)

    def _verify_addresses(self, addresses: Dict[str, str]):
        # TODO: replace with UserSocket NewType the ports names.
        ports = [PUB_Socket, PUB_Socket_Server]
        for port in ports:
            if port not in addresses:
                raise Exception(f'Not enough ports {port} were passed to {self.name}')
        from utilities.myfunc import verify_port
        # Check only publisher port availability
        port = verify_port(addresses[PUB_Socket])
        local_ip = get_local_ip()
        self.addresses[PUB_Socket] = f'tcp://{local_ip}:{port}'
        self.addresses[PUB_Socket_Server] = addresses[PUB_Socket_Server].replace(" ", "").split(',')

    def _wait_server_hb(self) -> MessageExt:
        if FRONTEND_Server not in self.addresses or BACKEND_Server not in self.addresses:
            wait = True
        else:
            wait = False
        i = 0
        msg_out = None
        while wait and self.active:
            if i > 100:
                info_msg(self, 'INFO', f'{self.name} could not connect to server, no sockets, '
                                       f'try to restart {self.parent.name}')
                i = 0
            i += 1
            sockets = dict(self.poller.poll(100))
            if self.sockets[SUB_Socket] in sockets:
                mes, crypted = self.sockets[SUB_Socket].recv_multipart()
                # TODO: decrypt message safely with try except
                msg: MessageExt = MessageExt.msgpack_bytes_to_msg(mes)
                # TODO: first heartbeat could be received only from server! make it safe
                if msg.com == MsgComExt.HEARTBEAT_FULL.msg_name:
                    try:
                        info: HeartBeatFull = msg.info
                        sockets = info.device_public_sockets
                        if FRONTEND_Server in sockets and BACKEND_Server in sockets:
                            #TODO: need to check if it true SERVER using password or certificate
                            info_msg(self, 'INFO', f'{msg.short()}')
                            info_msg(self, 'INFO', f'Info from Server is obtained for messenger operation.')
                            self.addresses[FRONTEND_Server] = sockets[BACKEND_Server]
                            self.addresses[BACKEND_Server] = sockets[BACKEND_Server]
                            msg_out = msg
                            break
                        else:
                            raise MessengerError(f'Not all sockets are sent to {self.name}')
                    except (AttributeError, Exception) as e:  # IN case when short Heartbeat arrived
                        pass
        return msg_out


class ServiceMessenger(ClientMessenger):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class ServerMessenger(Messenger):
    """
    Server Messenger represents router-router + Publisher + Subsriber sockets
    Backend ROUTER socket connects to Services using tcp://backend
    Messenger Sub socket is used to receive service updates on their status (heartbeat)
    addresses:
    frontend: tcp://local_IP:xxxx
    backend: tcp://local_IP:xxxx+1
    publisher: tcp://local_IP:xxxx+2
    services1 to n: tcp://local_IP:xxxx+3+n

    """

    sockets_names = set([FRONTEND_Server, BACKEND_Server, PUB_Socket_Server])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # TODO: when connection is deleted from device these pools must be updated
        self._frontendpool = set()
        self._backendpool = set()

    def _create_sockets(self):
        try:
            self.context = zmq.Context()
            frontend = self.context.socket(zmq.ROUTER)
            frontend.bind(self.addresses[FRONTEND_Server])
            backend = self.context.socket(zmq.ROUTER)
            backend.bind(self.addresses[BACKEND_Server])

            publisher = self.context.socket(zmq.PUB)
            publisher.bind(self.addresses[PUB_Socket_Server])

            # SOCKET SUBSCRIBER
            sub = self.context.socket(zmq.SUB)

            self.poller = zmq.Poller()
            self.poller.register(frontend, zmq.POLLIN)
            self.poller.register(backend, zmq.POLLIN)
            self.poller.register(sub, zmq.POLLIN)

            self.sockets = {FRONTEND_Server: frontend,
                            BACKEND_Server: backend,
                            PUB_Socket_Server: publisher,
                            SUB_Socket: sub}
            self.public_sockets = {PUB_Socket_Server: self.addresses[PUB_Socket_Server],
                                   FRONTEND_Server: self.addresses[FRONTEND_Server],
                                   BACKEND_Server: self.addresses[BACKEND_Server]}
        except (WrongAddress, KeyError, zmq.ZMQError) as e:
            error_logger(self, self._create_sockets, e)
            raise e

    def _deal_with_reaceived_msg(self, msgs: List[MsgTuple]):
        for msg, device_id, socket_name, crypted in msgs:
            try:
                if int(crypted):
                    msg: bytes = self.decrypt_with_session_key(msg, device_id)
                mes: MessageExt = MessageExt.msgpack_bytes_to_msg(msg)
                self.parent.thinker.add_task_in(mes)
            except (MessengerError, MessageError, ThinkerError, Exception) as e:
                error_logger(self, self.run, e)
                msg_r = self.parent.generate_msg(msg_com=MsgComExt.ERROR,
                                                 error_comments=str(e),
                                                 reply_to='', receiver_id=device_id)
                self.add_msg_out(msg_r)

    def gen_symmetric_key(self, device_id) -> bytes:
        """
        Session key is generated based on PBKDF2 standard, the key is stored in connected_fernets dict
        :param device_id: unique device id
        :return: None
        """
        salt = Fernet.generate_key()
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000, backend=default_backend())
        password = Fernet.generate_key()
        return base64.urlsafe_b64encode(kdf.derive(password))

    def info(self):
        from collections import OrderedDict as od
        info: od = super().info()
        info['pools'] = {'frontend': self._frontendpool, 'backend': self._backendpool}
        return info

    def run(self):
        super().run()
        try:
            info_msg(self, 'STARTED')
            self._receive_msgs()
        except zmq.error.ZMQError as e:  # Bad kind of error!
            error_logger(self, self.run, e)
            self.stop()
        finally:
            for _, soc in self.sockets.items():
                soc.close()
            self.context.destroy()
            self.active = False
            self.paused = True
            info_msg(self, 'STOPPED')

    def _receive_msgs(self):
        msgs = []
        while self.active:
            if not self.paused:
                sockets = dict(self.poller.poll(1))
                try:
                    if self.sockets[FRONTEND_Server] in sockets:
                        device_id, msg, crypted = self.sockets[FRONTEND_Server].recv_multipart()
                        device_id = device_id.decode('utf-8')
                        if device_id not in self._frontendpool:
                            self._frontendpool.add(device_id)
                        msgs.append(MsgTuple(msg, device_id, FRONTEND_Server, crypted))
                    if self.sockets[BACKEND_Server] in sockets:
                        device_id, msg, crypted = self.sockets[BACKEND_Server].recv_multipart()
                        device_id = device_id.decode('utf-8')
                        if device_id not in self._backendpool:
                            self._backendpool.add(device_id)
                        msgs.append(MsgTuple(msg, device_id, BACKEND_Server, crypted))
                    if self.sockets[SUB_Socket] in sockets:
                        msg, crypted = self.sockets[SUB_Socket].recv_multipart()
                        msgs.append(MsgTuple(msg, None, SUB_Socket, crypted))
                    if msgs:
                        self._deal_with_reaceived_msg(msgs)
                        msgs = []
                except ValueError as e:
                    self.logger.error(e)

    def send_msg(self, msg: MessageExt):
        try:
            crypted = str(int(msg.crypted)).encode('utf-8')
            msg_bytes = self.encrypt_with_session_key(msg)
            if msg.receiver_id == '':
                self.sockets[PUB_Socket_Server].send_multipart([msg_bytes, crypted])
            else:
                if msg.receiver_id in self._frontendpool:
                    self.sockets[FRONTEND_Server].send_multipart([msg.receiver_id.encode('utf-8'), msg_bytes, crypted])
                    info_msg(self, 'INFO', f'Msg {msg.id}, com {msg.com} is send from frontend to {msg.receiver_id}.')
                elif msg.receiver_id in self._backendpool:
                    self.sockets[BACKEND_Server].send_multipart([msg.receiver_id.encode('utf-8'), msg_bytes, crypted])
                    info_msg(self, 'INFO', f'Msg {msg.id}, com {msg.com} is send from backend to {msg.receiver_id}.')
                else:
                    error_logger(self, self.send_msg, f'ReceiverID {msg.receiver_id} is not present in Server pool.')
        except zmq.ZMQError as e:
            error_logger(self, self.send_msg, e)

    def _verify_addresses(self, addresses: Dict[str, str]):
        if not isinstance(addresses, dict):
            raise Exception(f'{addresses} are not dict, func: {self._verify_addresses.__name__} of {self.parent.name}')

        from utilities.myfunc import verify_port
        excluded = []
        local_ip = get_local_ip()
        for port in self.sockets_names:
            if port not in addresses:
                raise Exception(f'Not enough ports {port} were passed to {self.name}')
            port_n = verify_port(addresses[port], excluded)
            excluded.append(port_n)
            self.addresses[port] = f'tcp://{local_ip}:{port_n}'

