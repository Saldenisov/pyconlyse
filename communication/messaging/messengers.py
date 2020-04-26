import logging
import base64
from abc import abstractmethod
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from time import sleep
from typing import Dict, Union, List

import zmq
from devices.devices import Device
from communication.interfaces import MessengerInter
from communication.messaging.message_utils import MsgGenerator
from errors.messaging_errors import MessengerError
from errors.myexceptions import WrongAddress, ThinkerError
from utilities.data.datastructures.mes_dependent.dicts import OrderedDictMod
from utilities.data.messaging import Message, MsgType
from utilities.myfunc import unique_id, info_msg, error_logger, get_local_ip, get_free_port
from utilities.tools.decorators import make_loop


module_logger = logging.getLogger(__name__)


class Messenger(MessengerInter):

    n_instance = 0

    def __init__(self,
                 name: str,
                 addresses: Dict[str, str],
                 parent: Union[Device],
                 pub_option: bool,
                 **kwargs):
        super().__init__()
        self._attempts_to_restart_sub = 1
        self._are_you_alive_send = False
        Messenger.n_instance += 1
        self.logger = logging.getLogger(f'{__name__}.{self.__class__.__name__}')
        self.name = f'{self.__class__.__name__}:{Messenger.n_instance}:{name}:{get_local_ip()}'
        self.parent: Union[Device, Messenger] = None
        if parent:
            self.id: str = parent.id
            self.parent: Union[Device] = parent
        else:
            self.parent = self
            self.id = f'{self.name}:{unique_id(self.name)}'
            self.pyqtsignal_connected = False
        self.active = False
        self.paused = False
        self._msg_out = OrderedDictMod(name=f'msg_out:{self.parent.id}')
        # ZMQ sockets, communication info
        self.sockets = {}
        self._public_sockets = {}
        self.addresses = {}
        self._pub_option = pub_option
        if self.parent:
            try:
                self._polling_time = int(self.parent.get_general_settings()['polling']) / 1000.
            except AttributeError:
                self._polling_time = 1
        else:
            self._polling_time = 1
        # Cryptographic rsa keys are generated here
        self._fernet: Fernet = None
        self._gen_rsa_keys()

        info_msg(self, 'INITIALIZING')
        try:
            self._verify_addresses(addresses)
            self._create_sockets()
            info_msg(self, 'INITIALIZED')
        except (WrongAddress, ThinkerError, zmq.ZMQError) as e:
            info_msg(self, 'NOT INITIALIZED')
            raise MessengerError(str(e))

    def add_msg_out(self, msg: Message):
        try:
            if len(self._msg_out) > 100000:
                self._msg_out.popitem(False)  # pop up last item
                self.logger.info('Dict of msg_out is overfull > 100000 msg')
            self._msg_out[msg.id] = msg
        except KeyError as e:
            error_logger(self, self.add_msg_out, e)

    @abstractmethod
    def _create_sockets(self):
        pass

    def create_fernet(self, session_key: bytes):
        return Fernet(session_key)

    def decrypt_with_private(self, cipher_text: bytes):
        plaintext = self._private_key.decrypt(cipher_text, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()),
                                                                        algorithm=hashes.SHA1(), label=None))
        return plaintext

    def decrypt_with_session_key(self, msg_json: bytes, fernet: Fernet = None):
        # TODO: add functionality to messenger.decrypt() when TLS is realized
        if not fernet:
            fernet = self._fernet
        return fernet.decrypt(msg_json)

    def encrypt_with_session_key(self, msg_json: bytes, fernet: Fernet = None):
        # TODO: add functionality to messenger.encrypt() when TLS is realized
        if not fernet:
            fernet = self._fernet
        return fernet.encrypt(msg_json)

    @property
    def fernet(self):
        return self._fernet

    @fernet.setter
    def fernet(self, value):
        self._fernet = value

    def _gen_rsa_keys(self):
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        self._public_key = self._private_key.public_key()

    def heartbeat(self) -> Message:
        return Message(com='heartbeat', type=MsgType.INFO, )

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

    @property
    def public_sockets(self):
        return self._public_sockets

    @public_sockets.setter
    def public_sockets(self, value):
        self._public_sockets = value

    @property
    def public_key(self):
        return self._public_key.public_bytes(encoding=serialization.Encoding.PEM,
                                             format=serialization.PublicFormat.SubjectPublicKeyInfo)

    def pause(self):
        "put executation of thread on pause"
        self.paused = True
        self.logger.info(f'{self.name} is paused')
        sleep(0.01)

    @abstractmethod
    def run(self):
        info_msg(self, 'STARTING')
        self.active = True
        self.paused = False
        # Start send loop here
        self._sendloop_logic(await_time=0.1 / 1000.)

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
    def send_msg(self, msg: Message):
        pass

    @make_loop
    def _sendloop_logic(self, await_time):
        if len(self._msg_out) > 0:
            msg: Message = self._msg_out.popitem(last=False)[1]
            self.send_msg(msg)

    def stop(self):
        info_msg(self, 'STOPPING')
        self.active = False
        self.paused = False
        self._msg_out = {}

    def subscribe_sub(self, address=None, filter_opt=b""):
        try:
            self.sockets['sub'].connect(address)
            self.sockets['sub'].setsockopt(zmq.SUBSCRIBE, filter_opt)
            self.sockets['sub'].setsockopt(zmq.RCVHWM, 3)
            self.logger.info(f'socket sub is connected to {address}')
        except (zmq.ZMQError, Exception) as e:
            error_logger(self, self.subscribe_sub, e)

    @abstractmethod
    def _verify_addresses(self, addresses: dict):
        pass

    def unpause(self):
        "unpauses executation of thread"
        self.paused = False
        self.logger.info(f'{self.name} is unpaused')


class ClientMessenger(Messenger):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _create_sockets(self):
        try:
            self.context = zmq.Context()
            # SOCKET DEALER
            dealer = self.context.socket(zmq.DEALER)
            dealer.setsockopt_unicode(zmq.IDENTITY, self.id)
            # SOCKET SUBSCRIBER
            sub = self.context.socket(zmq.SUB)
            sub.setsockopt(zmq.RCVHWM, 3)
            # SOCKET PUBLISHER
            if self._pub_option:
                publisher = self.context.socket(zmq.PUB)
                publisher.setsockopt_unicode(zmq.IDENTITY, self.addresses['publisher'])
                self.sockets = {'dealer': dealer, 'sub': sub, 'publisher': publisher}
                self.public_sockets = {'publisher': self.addresses['publisher']}
            else:
                self.sockets = {'dealer': dealer, 'sub': sub}

            # POLLER
            self.poller = zmq.Poller()
            self.poller.register(dealer, zmq.POLLIN)
            self.poller.register(sub, zmq.POLLIN)
        except (WrongAddress, KeyError, zmq.ZMQError) as e:
            error_logger(self, self._create_sockets, e)
            raise e

    def _verify_addresses(self, addresses: dict):
        ports = ['publisher', 'server_publisher']
        for port in ports:
            if port not in addresses:
                raise Exception(f'Not enough ports {port} were passed to {self.name}')
        from utilities.myfunc import verify_port
        # Check only publisher port availability
        port = verify_port(addresses['publisher'])
        local_ip = get_local_ip()
        self.addresses['publisher'] = f'tcp://{local_ip}:{port}'
        self.addresses['server_publisher'] = addresses['server_publisher'].replace(" ", "").split(',')

    def connect(self):
        try:
            self.sockets['dealer'].connect(self.addresses['server_frontend'])
            if self._pub_option:
                try:
                    self.sockets['publisher'].bind(self.addresses['publisher'])
                except (WrongAddress, zmq.error.ZMQError) as e:
                    error_logger(self, self.connect, e)
                    port = get_free_port(scope=None)
                    local_ip = get_local_ip()
                    self.addresses['publisher'] = f'tcp://{local_ip}:{port}'
                    self.public_sockets = {'publisher': self.addresses['publisher']}
                    self.sockets['publisher'].setsockopt_unicode(zmq.IDENTITY, self.addresses['publisher'])
                    self.sockets['publisher'].bind(self.addresses['publisher'])
        except (WrongAddress, zmq.error.ZMQError) as e:
            error_logger(self, self.connect, e)

    def info(self):
        return super().info()

    def run(self):
        super().run()
        self._wait_server_hb()
        try:
            if self.active:
                self.connect()
                info_msg(self, 'STARTED')
            msgs = []
            while self.active:
                try:
                    if not self.paused:
                        sockets = dict(self.poller.poll(1))
                        if self.sockets['dealer'] in sockets:
                            msg, crypted = self.sockets['dealer'].recv_multipart()  # TODO: check how the wrong msg will be treated when the param CRYPTED is not available
                            msgs.append((msg,crypted))
                        if self.sockets['sub'] in sockets:
                            msg, crypted = self.sockets['sub'].recv_multipart()
                            msgs.append((msg, crypted))
                        if sockets:
                            for msg, crypted in msgs:
                                try:
                                    if int(crypted):
                                        msg = self.decrypt_with_session_key(msg)
                                    mes: Message = MsgGenerator.json_to_message(msg)
                                    self.parent_thinker.add_task_in(mes)
                                except Exception as e:
                                    error_logger(self, self.run, str(e))
                                    pass  # TODO: if error send back error!
                            msgs = []
                    else:
                        sleep(.1)
                except ValueError as e:  # TODO when recv_multipart works wrong!
                    self.logger.error(e)

        except (zmq.ZMQError, Exception) as e:
            error_logger(self, self.run, e)
            self.stop()
        finally:
            self.sockets['dealer'].close()
            if self.sockets['sub']:
                self.sockets['sub'].close()
            self.context.destroy()
            info_msg(self, 'STOPPED')

    def send_msg(self, msg: Message):
        try:
            crypted = str(int(msg.crypted)).encode('utf-8')
            msg_json = msg.json_repr()
            if msg.crypted:
                msg_json = self.encrypt_with_session_key(msg_json)
            if msg.body.type == MsgType.REPLY or msg.body.type == MsgType.DEMAND:
                self.sockets['dealer'].send_multipart([msg_json, crypted])
                self.logger.info(f'{msg.short()} is send from {self.parent.name}')
            elif msg.body.type == MsgType.INFO:
                if self._pub_option:
                    self.sockets['publisher'].send_multipart([msg_json, crypted])
                else:
                    self.logger.info('Publisher socket is not avaiable')
            else:
                error_logger(self, self.send_msg, f'Wrong msg.body.type: {msg.body.type}')
        except zmq.ZMQError as e:
            error_logger(self, self.send_msg, e)

    def _wait_server_hb(self):
        if 'server_frontend' not in self.addresses or 'server_backend' not in self.addresses:
            wait = True
        else:
            wait = False
        i = 0
        while wait and self.active:
            if i > 100:
                self.logger.info(f'{self.name} could not connect to server, no sockets, '
                                 f'try to restart {self.parent.name}')
                i = 0
            i += 1
            sockets = dict(self.poller.poll(100))
            if self.sockets['sub'] in sockets:
                mes, crypted = self.sockets['sub'].recv_multipart()
                mes: Message = MsgGenerator.json_to_message(mes)
                # first heartbeat in principle could be received only from server
                if mes.data.com == MsgGenerator.HEARTBEAT.mes_name:
                    sockets = mes.data.info.sockets
                    if 'frontend' in sockets and 'backend' in sockets:
                        self.logger.info(mes)
                        self.addresses['server_frontend'] = sockets['frontend']
                        self.addresses['server_backend'] = sockets['backend']
                        self.parent.server_msgn_id = mes.body.sender_id
                        wait = False
                    else:
                        raise Exception(f'Not all sockets are sent to {self.name}')


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

    sockets_names = ['frontend', 'backend', 'publisher']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # TODO: when connection is deleted from device these pools must be updated
        self._frontendpool: set = set()
        self._backendpool: set = set()
        self.fernets: Dict[str, Fernet] = {}

    def _verify_addresses(self, addresses):
        if not isinstance(addresses, dict):
            raise Exception(f'{addresses} are not dict, func: {self._verify_addresses.__name__} of {self.parent.name}')

        ports = ['publisher', 'frontend', 'backend']
        from utilities.myfunc import verify_port
        excluded = []
        local_ip = get_local_ip()
        for port in ports:
            if port not in addresses:
                raise Exception(f'Not enough ports {port} were passed to {self.name}')
            port_n = verify_port(addresses[port], excluded)
            excluded.append(port_n)
            self.addresses[port] = f'tcp://{local_ip}:{port_n}'

    def _create_sockets(self):
        try:
            self.context = zmq.Context()
            frontend = self.context.socket(zmq.ROUTER)
            frontend.bind(self.addresses['frontend'])
            backend = self.context.socket(zmq.ROUTER)
            backend.bind(self.addresses['backend'])

            publisher = self.context.socket(zmq.PUB)
            publisher.bind(self.addresses['publisher'])

            # SOCKET SUBSCRIBER
            sub = self.context.socket(zmq.SUB)

            self.poller = zmq.Poller()
            self.poller.register(frontend, zmq.POLLIN)
            self.poller.register(backend, zmq.POLLIN)
            self.poller.register(sub, zmq.POLLIN)

            self.sockets = {'frontend': frontend,
                            'backend': backend,
                            'publisher': publisher,
                            'sub': sub}
            self.public_sockets = {'publisher': self.addresses['publisher'],
                                    'frontend': self.addresses['frontend'],
                                    'backend': self.addresses['backend']}
        except (WrongAddress, KeyError, zmq.ZMQError) as e:
            error_logger(self, self._create_sockets, e)
            raise e

    def info(self):
        from collections import OrderedDict as od
        info: od = super().info()
        info['pools'] = {'frontend': self._frontendpool, 'backend': self._backendpool}
        return info

    def run(self):
        super().run()
        try:
            info_msg(self, 'STARTED')
            msgs = []
            while self.active:
                if not self.paused:
                    sockets = dict(self.poller.poll(1))
                    try:
                        if self.sockets['frontend'] in sockets:
                            device_id, msg, crypted = self.sockets['frontend'].recv_multipart()
                            device_id = device_id.decode('utf-8')
                            if device_id not in self._frontendpool:
                                self._frontendpool.add(device_id)
                            msgs.append((msg, crypted))
                        if self.sockets['backend'] in sockets:
                            device_id, msg, crypted = self.sockets['backend'].recv_multipart()
                            device_id = device_id.decode('utf-8')
                            if device_id not in self._backendpool:
                                self._backendpool.add(device_id)
                            msgs.append((msg, crypted))
                        if self.sockets['sub'] in sockets:
                            msg, crypted = self.sockets['sub'].recv_multipart()
                            msgs.append((msg, crypted))
                        if sockets:
                            # TODO: but what happends if there is not crypted arrived!!!???
                            for msg, crypted in msgs:
                                try:
                                    if int(crypted):
                                        # TODO: if there is no Fernet send msg back crypted as it is
                                        fernet = self.fernets[device_id]
                                        msg = self.decrypt_with_session_key(msg, fernet)
                                    mes: Message = MsgGenerator.json_to_message(msg)
                                    self.parent_thinker.add_task_in(mes)
                                except Exception as e:
                                    error_logger(self, self.run, str(e))
                                    pass  # TODO: send back with ERROR
                            msgs = []
                    except ValueError as e:
                        self.logger.error(e)
                else:
                    sleep(0.1)
        except zmq.error.ZMQError as e:
            error_logger(self, self.run, e)
            self.stop()
        finally:
            for _, soc in self.sockets.items():
                soc.close()
            self.context.destroy()
            info_msg(self, 'STOPPED')

    def gen_symmetric_key(self, device_id):
        salt = Fernet.generate_key()
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000, backend=default_backend())
        password = Fernet.generate_key()
        session_key = base64.urlsafe_b64encode(kdf.derive(password))
        self.fernets[device_id] = Fernet(session_key)
        return session_key

    def encrypt_with_public(self, msg_b: bytes, pem: bytes):
        public_key = self._load_public_key(pem)
        msg_encrypted = public_key.encrypt(msg_b, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()),
                                                                                algorithm=hashes.SHA1(), label=None))
        return msg_encrypted

    def send_msg(self, msg: Message):
        try:
            crypted = str(int(msg.crypted)).encode('utf-8')
            msg_json = msg.json_repr()
            if msg.crypted:
                fernet = self.fernets[msg.body.receiver_id]
                msg_json = self.encrypt_with_session_key(msg_json, fernet)
            if msg.body.type == MsgType.INFO:
                #self.logger.info(f'Info msg {msg} is send from publisher')
                self.sockets['publisher'].send_multipart([msg_json, crypted])
                if self.parent.pyqtsignal_connected:
                    self.parent.signal.emit(msg)
            elif msg.body.type != MsgType.INFO:
                if msg.body.receiver_id in self._frontendpool:
                    self.sockets['frontend'].send_multipart([msg.body.receiver_id.encode('utf-8'), msg_json, crypted])
                    self.logger.info(f'{msg.body.type} msg {msg.id} is send from frontend')
                elif msg.body.receiver_id in self._backendpool:
                    self.sockets['backend'].send_multipart([msg.body.receiver_id.encode('utf-8'), msg_json, crypted])
                    self.logger.info(f'{msg.body.type} msg {msg.id} is send from backend')
                else:
                    error_logger(self, self.send_msg, f'Receiver ID does not exist: {msg.body.receiver_id}')
            else:
                error_logger(self, self.send_msg, f'Wrong msg.body.type: {msg.body.type}')
        except zmq.ZMQError as e:
            error_logger(self, self.send_msg, e)

