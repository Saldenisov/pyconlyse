from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from inspect import signature, isclass
from pathlib import Path
import sys
import sqlite3 as sq3
from time import sleep
from typing import Any, Callable, List, Tuple, Union

from PyQt5.QtCore import QObject, pyqtSignal

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(Path(__file__).resolve().parents[1]))

from datastructures.mes_dependent.dicts import Connections_Dict
from devices.interfaces import DeviceInter
from communication.messaging.messages import *
from communication.messaging.message_utils import MsgGenerator
from utilities.database.tools import db_create_connection, db_execute_select
from utilities.errors.messaging_errors import MessengerError
from utilities.errors.myexceptions import DeviceError
from utilities.configurations import configurationSD
from utilities.myfunc import info_msg, unique_id, error_logger
from logs_pack import initialize_logger

module_logger = logging.getLogger(__name__)


pyqtWrapperType = type(QObject)


class FinalMeta(type(DeviceInter), type(QObject)):
    pass


class Device(QObject, DeviceInter, metaclass=FinalMeta):
    """
    Device is an abstract class, predetermining the real devices both for software and devices soft
    """
    n_instance = 0

    signal = pyqtSignal(MessageInt)

    def __init__(self, name: str, db_path: Path, cls_parts: Dict[str, Any], type: DeviceType, parent: QObject = None,
                 db_command: str = '', logger_new=True, test=False, **kwargs):
        super().__init__()
        Device.n_instance += 1
        self.available_public_functions_names = list(cmd.name for cmd in self.available_public_functions())
        self.config = configurationSD(self)
        self.connections: Dict[DeviceId, Connection] = {}
        self.cls_parts: Dict[str, Union[ThinkerInter, MessengerInter, ExecutorInter]] = cls_parts
        self.device_status: DeviceStatus = DeviceStatus(*[False] * 5)
        self.db_path = db_path
        self.name: str = name
        self._main_executor = ThreadPoolExecutor(max_workers=100)
        self.parent: QObject = parent
        self.type: DeviceType = type
        self.test = test

        if logger_new:
            self.logger = initialize_logger(app_folder / 'LOG', file_name=__name__ + '.' + self.__class__.__name__)
            if test:
                self.logger.setLevel(logging.ERROR)
        else:
            self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        if 'id' not in kwargs:
            self.id: DeviceId = f'{name}:{unique_id(name)}'
        else:
            self.id: DeviceId = kwargs['id']

        try:
            assert len(self.cls_parts) == 2
            for key, item in self.cls_parts.items():
                assert key in ['Messenger', 'Thinker']
                assert isclass(item)
        except AssertionError as e:
            self.logger.error(e)
            raise e

        try:
            pyqtslot: Callable = kwargs['pyqtslot']
            self._connect_pyqtslot_signal(pyqtslot)
        except KeyError:
            self.pyqtsignal_connected = False
            self.logger.info(f'pyqtsignal is set to False')

        # config is set here
        try:
            db_conn = db_create_connection(self.db_path)
            res, comments = db_execute_select(db_conn, db_command)
            db_conn.close()
            self.config.add_config(self.name, config_text=res)

            from communication.messaging.messengers import Messenger
            from communication.logic.thinkers_logic import Thinker

            if 'pub_option' not in kwargs:
                kwargs['pub_option'] = True

            self.messenger: Messenger = self.cls_parts['Messenger'](name=self.name,
                                                                    addresses=self.get_addresses(),
                                                                    parent=self,
                                                                    pub_option=kwargs['pub_option'])
            self.thinker: Thinker = self.cls_parts['Thinker'](parent=self)
        except (sq3.Error, KeyError, MessengerError) as e:
            self.logger.error(e)
            raise DeviceError(str(e))

        info_msg(self, 'CREATED')

    def active_connections(self) -> List[Tuple[DeviceId, DeviceType]]:
        res = []
        for device_id, connection in self.connections.items():
            res.append((device_id, connection.device_name))
        return res

    @property
    @abstractmethod
    def available_services(self) -> Dict[DeviceId, str]:
        pass

    @abstractmethod
    def available_public_functions(self) -> Tuple[CmdStruct]:
        pass

    @abstractmethod
    def activate(self, flag: bool) -> Tuple[Union[bool, str]]:
        """
        Activates service, by connecting to hardware controller and reading settings
        :param flag: True/False
        :return: res, comments='' if True, else error_message
        """

    def add_to_executor(self, func, **kwargs) -> bool:
        # used for slow methods and functions
        try:
            self._main_executor.submit(func, **kwargs)
            return True
        except Exception as e:  # TODO: replace EXCEPTION with correct errors
            self.logger.error(e)
            return False

    def _connect_pyqtslot_signal(self, pyqtslot):
        # Pyqt slot and signal are connected
        self.signal.connect(pyqtslot)
        self.pyqtsignal_connected = True
        self.logger.info(f'pyqtsignal is set to True')

    @abstractmethod
    def description(self) -> Dict[str, Any]:
        """
        return descirption of device, configuration depends on device type: stpmtr, detector, etc.
        :return: Dict[str, Any]
        """
        pass

    def get_settings(self, name: str) -> Dict[str, Union[str, List[str]]]:
        try:
            return self.config.config_to_dict(self.name)[name]
        except ValueError as e:
            self.logger.error(e)
            raise

    def get_addresses(self) -> Dict[str, Union[str, List[str]]]:
        return self.get_settings('Addresses')

    def get_general_settings(self) -> Dict[str, Union[str, List[str]]]:
        return self.get_settings('General')

    def _get_list_db(self, from_section: str, what: str, type_value: Union[tuple, float, int, dict, str]) \
            -> List[Tuple[Union[float, int]]]:
        try:
            listed_param: List[Tuple[Union[float, int]]] = []
            listed_param_s: List[str] = self.config.config_to_dict(self.name)[from_section][what].replace(" ",
                                                                                                          "").split(';')
            for exp in listed_param_s:
                val = eval(exp)
                if not isinstance(val, type_value):
                    raise TypeError()
                listed_param.append(val)
            return listed_param
        except KeyError:
            raise DeviceError(f"_get_list_db: field {what} or section {from_section} is absent in the DB", self.name)
        except (TypeError, SyntaxError):
            raise DeviceError(f"_get_list_db: list param should be = (x1, x2); (x3, x4); or X1; X2;...", self.name)

    def generate_msg(self, msg_com: Union[MsgComInt, MsgComExt], **kwargs) -> Union[MessageExt, MessageInt, None]:
        """
        This function is dedicated to generate Messages for some device
        :param msg_com:
        :param kwargs: could be any, depends on the message definition
        :return: Union[MessageExt, MessageInt, None]
        """
        def gen_msg(self, msg_com: Union[MsgComInt, MsgComExt], **kwargs) -> Union[MessageExt, MessageInt, None]:
            try:
                message_info: MessageInfoExt = msg_com.value
                if not message_info.must_have_param.issubset(set(kwargs.keys())):
                    error_logger(self, self.generate_msg, f'Not all required parameters are given for {msg_com}'
                                                          f'{message_info.must_have_param}, only {kwargs.keys()}')
                    raise DeviceError(f'Not all parameters are passed to device.generate_msg')
                else:
                    if msg_com is MsgComExt.AVAILABLE_SERVICES:
                        info = AvailableServices(available_services=kwargs['available_services'])
                    elif msg_com is MsgComExt.HEARTBEAT or msg_com is MsgComInt.HEARTBEAT:
                        event = kwargs['event']
                        info = HeartBeat(device_id=self.id, event_n=event.n, event_id=event.id)
                    elif msg_com is MsgComExt.HEARTBEAT_FULL:
                        event = kwargs['event']
                        info = HeartBeatFull(event_n=event.n, event_name=event.external_name, event_tick=event.tick,
                                             event_id=event.id, device_id=self.id,
                                             device_name=self.name, device_type=self.type,
                                             device_public_key=self.messenger.public_key,
                                             device_public_sockets=self.messenger.public_sockets)
                    elif msg_com is MsgComExt.ERROR:
                        info = MsgError(error_comments=kwargs['error_comments'])
                    elif msg_com is MsgComInt.DEVICE_INFO_INT:
                        info = DeviceInfoInt(active_connections=self.active_connections(),
                                             available_public_functions=self.available_public_functions(),
                                             device_id=self.id,
                                             device_status=self.device_status, device_description=self.description(),
                                             events_running=list(self.thinker.events.name_id.keys()))
                    elif msg_com is MsgComExt.SHUTDOWN:
                        info = ShutDown(device_id=self.id, reason=kwargs['reason'])
                    elif msg_com is MsgComExt.WELCOME_INFO_SERVER:
                        try:
                            session_key = self.connections[kwargs['receiver_id']].session_key
                            device_public_key = self.connections[kwargs['receiver_id']].device_public_key
                            # Session key Server-Device is crypted with device public key, message is not crypted
                            session_key_crypted = self.messenger.encrypt_with_public(session_key, device_public_key)
                        except KeyError:
                            session_key_crypted = b''
                        finally:
                            info = WelcomeInfoServer(session_key=session_key_crypted)

                    elif msg_com is MsgComExt.WELCOME_INFO_DEVICE:
                        server_public_key = self.connections[self.server_id].device_public_key
                        pub_key = self.messenger.public_key
                        device_public_key_crypted = self.messenger.encrypt_with_public(pub_key,
                                                                                       server_public_key)
                        event = kwargs['event']
                        info = WelcomeInfoDevice(event_name=event.external_name, event_tick=event.tick,
                                                 event_id=event.id, device_id=self.id, device_name=self.name,
                                                 device_type=self.type, device_public_key=device_public_key_crypted,
                                                 device_public_sockets=self.messenger.public_sockets)
            except Exception as e:  # TODO: replace Exception, after all it is needed for development
                error_logger(self, self.generate_msg, f'{msg_com}: {e}')
                raise e
            finally:
                if isinstance(msg_com, MsgComExt):
                    if msg_com.msg_type is MsgType.BROADCASTED:
                        reply_to = ''
                        receiver_id = ''
                    elif msg_com.msg_type is MsgType.DIRECTED:
                        try:
                            reply_to = kwargs['reply_to']
                        except KeyError:
                            reply_to = ''
                        receiver_id = kwargs['receiver_id']

                    return MessageExt(com=msg_com.msg_name, crypted=msg_com.msg_crypted, info=info,
                                      receiver_id=receiver_id,
                                      reply_to=reply_to, sender_id=self.messenger.id)
                else:
                    return MessageInt(com=msg_com.msg_name, info=info, sender_id=self.messenger.id)
        if not (isinstance(msg_com, MsgComExt) or isinstance(msg_com, MsgComInt)):
            error_logger(self, self.generate_msg, f'Wrong msg_com is passed, not MsgCom')
            return None
        else:
            return gen_msg(self, msg_com, **kwargs)

    def execute_com(self, msg: MessageExt):
        error = False
        info: DoIt = msg.data.info
        com: str = info.com
        input: FuncInput = info.input
        if com in self.available_public_functions_names:
            f = getattr(self, com)
            func_input_type = signature(f).parameters['func_input'].annotation
            if func_input_type == type(input):
                try:
                    result: FuncOutput = f(input)
                    msg_i = MsgGenerator.done_it(self, msg_i=msg, result=result)
                except Exception as e:
                    self.logger.error(e)
                    error = True
                    comments = str(e)
            else:
                error = True
                comments = f'Device {self.id} function: execute_com: Input type: {type(input)} do not match to ' \
                           f'func_input type : {func_input_type}'
        else:
            error = True
            comments = f'com: {com} is not available for Service {self.id}. See {self.available_public_functions()}'
        if error:
            msg_i = MsgGenerator.error(self, msg_i=msg, comments=comments)
        self.thinker.msg_out(True, msg_i)

    @staticmethod
    def exec_mes_every_n_sec(f: Callable[[Any], bool], delay=5, n_max=10, specific={}) -> None:
        i = 0
        if delay > 5:
            delay = 5
        from time import sleep
        flag = True
        while flag and i <= n_max:
            i += 1
            sleep(delay)
            if f:
                flag = f(**specific)

    def pause(self):
        self.thinker.pause()
        self.messenger.pause()
        self.device_status.messaging_paused = True
        self.send_status_pyqt()

    @property
    def public_sockets(self):
        return self.messenger.public_sockets

    def unpause(self):
        self.messenger.unpause()
        self.thinker.unpause()
        self.device_status.messaging_paused = False
        self.send_status_pyqt()

    def start(self):
        self._start_messaging()

    def stop(self):
        self._stop_messaging()

    def _start_messaging(self):
        """Start messaging part of Device"""
        info_msg(self, 'STARTING')
        self.thinker.start()  # !!!Thinker must start before the messenger, always!!!!
        self.messenger.start()
        info_msg(self, 'STARTED')
        self.send_status_pyqt()

    def _stop_messaging(self):
        """Stop messaging part of Device"""
        info_msg(self, 'STOPPING')
        stop_msg = self.generate_msg(msg_com=MsgComExt.SHUTDOWN, reason='normal_shutdown')
        self.thinker.msg_out(stop_msg)
        sleep(0.1)
        self.thinker.pause()
        self.messenger.pause()
        self.thinker.stop()
        self.messenger.stop()
        self.send_status_pyqt()
        self.device_status.messaging_paused = False
        self.device_status.messaging_on = False
        info_msg(self, 'STOPPED')

    @abstractmethod
    def send_status_pyqt(self):
        pass

    def send_msg_externally(self, msg: MessageExt):
        self.messenger.add_msg_out(msg)

    def update_config(self, message: str):
        # TODO: realize
        self.logger.info('Config is updated: ' + message)


class Server(Device):
    # TODO: refactor
    GET_AVAILABLE_SERVICES = CmdStruct('get_available_services', FuncAvailableServicesInput, FuncAvailableServicesOutput)
    MAKE_CONNECTION = CmdStruct('make_connection', None, None)

    def __init__(self, **kwargs):
        from communication.messaging.messengers import ServerMessenger

        if 'thinker_cls' in kwargs:
            cls_parts = {'Thinker': kwargs['thinker_cls'],
                         'Messenger': ServerMessenger}
        else:
            raise Exception('Thinker cls was not passed to Device factory')

        kwargs['cls_parts'] = cls_parts

        if 'db_command' not in kwargs:
            raise Exception('DB_command_type is not determined')
        super().__init__(**kwargs)
        self.device_status = DeviceStatus(active=True, power=True)  # Power is always ON for server and it is active

    @property
    def available_services(self) -> Dict[DeviceId, str]:
        available_services = {}
        for device_id, connection in self.connections.items():
            if connection.device_type is DeviceType.SERVICE:
                available_services[device_id] = connection.device_name
        return available_services

    @property
    def available_clients(self) -> Dict[str, str]:
        """Returns dict of running clients {receiver_id: name}"""
        clients_running = {}
        for device_id, connection in self.connections.items():
            if connection.device_type is DeviceType.CLIENT:
                clients_running[device_id] = connection.device_name
        return clients_running

    def activate(self, flag: bool):
        """Server is always active"""
        self.logger.info("""Server is always active""")

    def get_available_services(self, func_input: FuncAvailableServicesInput) -> FuncAvailableServicesOutput:
        """Returns dict of avaiable services {DeviceID: name}"""
        return FuncAvailableServicesOutput(comments='', func_success=True,  device_id=self.id,
                                           device_available_services=self.available_services)

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return (Server.GET_AVAILABLE_SERVICES, Server.MAKE_CONNECTION)

    def description(self) -> Desription:
        parameters = self.get_settings('Parameters')
        return Desription(info=parameters['info'], GUI_title=parameters['title'])

    def start(self):
        super().start()

    def send_status_pyqt(self):
        if self.pyqtsignal_connected:
            msg = self.generate_msg(msg_com=MsgComInt.DEVICE_INFO_INT, sender_id=self.id)
            if msg:
                self.signal.emit(msg)
        else:
            self.logger.info(f'pyqtsignal_connected is {self.pyqtsignal_connected}, the signal cannot be emitted')

    def set_default(self):
        pass


class Client(Device):
    """
    class Client communicates with Server to get access to Service it is bound to
    through service_devices determined within the model of PyQT application devoted to this task.
    """

    def __init__(self, **kwargs):
        from communication.messaging.messengers import ClientMessenger

        if 'thinker_cls' in kwargs:
            cls_parts = {'Thinker': kwargs['thinker_cls'],
                         'Messenger': ClientMessenger}
        else:
            raise Exception('Thinker cls was not passed to Device factory')

        kwargs['cls_parts'] = cls_parts
        # initialize_logger(app_folder / 'bin' / 'LOG', file_name=kwargs['name'])
        kwargs['type'] = DeviceType.CLIENT
        super().__init__(**kwargs)
        self.server_id = self.get_settings('General')['server_id']
        self.device_status = DeviceStatus(active=True, power=True)  # Power is always ON for client and it is active

    @property
    def available_services(self) -> Dict[DeviceId, str]:
        pass

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return ()

    def activate(self, flag: bool):
        """Client is always active"""
        self.logger.info("""Client is always active""")

    def description(self) -> Desription:
        # TODO: add functionality
        pass

    def execute_com(self, msg: MessageExt):
        pass

    def start(self):
        super().start()

    def send_status_pyqt(self):
        pass

    def set_default(self):
        pass


class Service(Device):
    ACTIVATE = CmdStruct('activate', FuncActivateInput, FuncActivateOutput)
    GET_CONTROLLER_STATE = CmdStruct('get_controller_state', FuncGetControllerStateInput, FuncGetControllerStateOutput)
    POWER = CmdStruct('power', FuncPowerInput, FuncPowerOutput)

    # TODO: Service and Client are basically the same thing. So they must be merged somehow
    def __init__(self, **kwargs):
        from communication.messaging.messengers import ServiceMessenger
        if 'thinker_cls' in kwargs:
            cls_parts = {'Thinker': kwargs['thinker_cls'],
                         'Messenger': ServiceMessenger}
        else:
            raise Exception('Thinker cls was not passed to Device factory')

        kwargs['cls_parts'] = cls_parts
        if 'db_command' not in kwargs:
            raise Exception('DB_command_type is not determined')
        kwargs['type'] = DeviceType.SERVICE
        super().__init__(**kwargs)
        self.server_id: DeviceId = self.get_settings('General')['server_id']

    @property
    def available_services(self) -> Dict[DeviceId, str]:
        pass

    @abstractmethod
    def activate(self, func_input: FuncActivateInput) -> FuncActivateOutput:
        pass

    @abstractmethod
    def available_public_functions(self) -> Tuple[CmdStruct]:
        return (Service.ACTIVATE, Service.GET_CONTROLLER_STATE, Service.POWER)

    @abstractmethod
    def _check_if_active(self) -> Tuple[bool, str]:
        """
        In real devices should ask hardware controller
        :return:
        """
        return self.device_status.active, ''

    @abstractmethod
    def _check_if_connected(self) -> Tuple[bool, str]:
        """
        In real devices should ask hardware controller
        :return:
        """
        return self.device_status.connected, ''

    @abstractmethod
    def description(self) -> Desription:
        pass

    @abstractmethod
    def get_controller_state(self, func_input: FuncGetControllerStateInput) -> FuncGetControllerStateOutput:
        pass

    def send_status_pyqt(self):
        pass

    def set_default(self):
        pass

    def power(self, func_input: FuncPowerInput) -> FuncPowerOutput:
        # TODO: to be realized in metal someday
        flag = func_input.flag
        if self.device_status.power ^ flag:  # XOR
            if not flag and self.device_status.active:
                comments = f'Power is {self.device_status.power}. Cannot switch power off when device is activated.'
                success = False
            else:
                self.device_status.power = flag
                success = True
                comments = f'Power is {self.device_status.power}. But remember, that user switches power manually...'
        else:
            success, comments = True, ''
        return FuncPowerOutput(comments=comments, device_status=self.device_status, func_success=success)


class DeviceFactory:
    # TODO: do refactoring with DeviceType and DeviceId, etc.
    @staticmethod
    def make_device(**kwargs):  #TODO: redefine kwargs
        if 'cls' in kwargs:
            cls: Device = kwargs['cls']
            if issubclass(cls, Device):
                return cls(**kwargs)
            elif type(cls).__name__ == 'str':
                raise BaseException('DeviceFactory Crash: Device cls is not a class, but str')
            else:
                raise BaseException(f'DeviceFactory Crash: Device cls is not a class, but {type(cls)}')
        else:
            if 'device_id' in kwargs and 'db_path' in kwargs:
                device_id: str = kwargs['device_id']

                db_conn = db_create_connection(kwargs['db_path'])
                device_name, comments = db_execute_select(db_conn, f"SELECT device_name from DEVICES_settings "
                                                                   f"where device_id='{device_id}'")

                if not device_name:
                    err = f'DeviceFactory Crash: {device_id} is not present in DB'
                    module_logger.error(err)
                    raise BaseException(err)

                project_type, comments = db_execute_select(db_conn, f"SELECT project_type from DEVICES_settings "
                                                                    f"where device_id='{device_id}'")

                from importlib import import_module
                module_comm_thinkers = import_module('communication.logic.thinkers_logic')
                if project_type == 'Client':
                    module_devices = import_module('devices.virtualdevices')
                    type = DeviceType.CLIENT
                elif project_type == 'Service':
                    module_devices = import_module('devices.service_devices')
                    type = DeviceType.SERVICE
                elif project_type == 'Server':
                    module_devices = import_module('devices.servers')
                    type = DeviceType.SERVER
                else:
                    raise Exception(f'Project type: {project_type} is not known')

                cls = getattr(module_devices, device_name)
                device_name_split = device_name.split('_')[0]
                if project_type != 'Server':
                    thinker_class = getattr(module_comm_thinkers, f'{device_name_split}{project_type}CmdLogic')
                else:
                    thinker_class = getattr(module_comm_thinkers, f'{device_name_split}CmdLogic')

                kwargs['name'] = device_name
                kwargs['thinker_cls'] = thinker_class
                kwargs['db_command'] = f'SELECT parameters from DEVICES_settings where device_id = "{device_id}"'
                kwargs['id'] = device_id
                kwargs['type'] = type
                if issubclass(cls, Device):
                    return cls(**kwargs)
            else:
                raise BaseException('DeviceFactory Crash: device_id or db_path were not passed')
