import sqlite3 as sq3
import sys
import logging
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict as od
from inspect import signature, isclass
from logs_pack import initialize_logger
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal
from time import sleep
from typing import Any, Callable, Dict, List, OrderedDict, Tuple, Union
from communication.interfaces import ThinkerInter, MessengerInter
from devices.interfaces import DeviceInter, DeviceId, DeviceType, ExecutorInter
from devices.devices_dataclass import (Connection, ControllerInfoExt, DeviceInfoInt, HardwareDevice,
                                       HardwareDeviceEssentials, HardwareDeviceDict,
                                       DeviceControllerStatus,
                                       FuncInput, FuncOutput, FuncAliveInput, FuncAliveOutput, FuncActivateInput,
                                       FuncAvailableServicesInput, FuncAvailableServicesOutput,
                                       FuncActivateOutput, FuncPowerInput, FuncActivateDeviceInput,
                                       FuncActivateDeviceOutput, FuncGetControllerStateInput,
                                       FuncGetControllerStateOutput, FuncServiceInfoInput, FuncServiceInfoOutput,
                                       FuncPowerOutput, ClientDescription,
                                       ServerDescription, ServiceDescription, PowerSettings,
                                       AvailableServices, HeartBeat, HeartBeatFull, ShutDown, WelcomeInfoDevice,
                                       WelcomeInfoServer)
from communication.messaging.messages import (MessageInt, MessageExt, MsgComInt, MsgError, MsgComExt, MsgType,
                                              MessageInfoExt)
from utilities.database.tools import db_create_connection, db_execute_select
from utilities.datastructures.mes_independent.general import CmdStruct
from utilities.errors.messaging_errors import MessengerError
from utilities.errors.myexceptions import DeviceError
from utilities.configurations import configurationSD
from utilities.myfunc import info_msg, unique_id, error_logger, join_smart_comments


app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(Path(__file__).resolve().parents[1]))
module_logger = logging.getLogger(__name__)


pyqtWrapperType = type(QObject)


class FinalMeta(type(DeviceInter), pyqtWrapperType):
    pass


class Device(QObject, DeviceInter, metaclass=FinalMeta):
    """
    Device is an abstract class, predetermining the real devices both for software and devices soft
    """
    n_instance = 0

    if pyqtSignal:
        signal = pyqtSignal(MessageInt)

    def __init__(self, name: str, db_path: Path, cls_parts: Dict[str, Any], type: DeviceType, parent: QObject = None,
                 db_command: str = '', logger_new=True, test=False, **kwargs):
        super().__init__()
        Device.n_instance += 1
        self.available_public_functions_names = list(cmd.name for cmd in self.available_public_functions())
        self.always_available_public_functions_names = list(cmd.name for cmd in self.always_available_public_functions())
        self.config = configurationSD(self)
        self.connections: Dict[DeviceId, Connection] = {}
        self.cls_parts: Dict[str, Union[ThinkerInter, MessengerInter, ExecutorInter]] = cls_parts
        self.ctrl_status: DeviceControllerStatus = DeviceControllerStatus(*[False] * 5)
        self.db_path = db_path
        self._fyi_msg_dict: OrderedDict[str, MessageInt] = od()
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
            raise DeviceError(self, str(e))

        from threading import Thread
        self._observing_func: Dict[str, List[Callable, int]] = {}
        self._observing_FLAG = True
        self._observing_locked = False
        self._observing_thread = Thread(name='observing_thread', target=self._observing)
        self._observing_thread.start()

        info_msg(self, 'CREATED')

    def _register_observation(self, name: str, func: Callable, every_n_sec=1):
        def register(self: Device, name: str, func: Callable, every_n_sec=1):
            if callable(func):
                self._observing_locked = True
                self._observing_func[name] = [func, int(every_n_sec)]
                self._observing_locked = False
            else:
                error_logger(self, self._register_observation, f'Func object {func} is not callable.')

        if not self._observing_locked:
            register(self, name, func, every_n_sec)
        else:
            for i in range(500):
                sleep(0.05)
                i += 1
                if not self._observing_locked:
                    register(self, name, func, every_n_sec)
                    break
                if i == 500:
                    error_logger(self, self._register_observation, f'Observing function was always locked, try again.')

    def _observing(self):
        info_msg(self, 'INFO', f'Observing thread started.')
        time = 0
        sleep_time = 0.5
        while self._observing_FLAG:
            sleep(sleep_time)
            time += sleep_time
            if not self._observing_locked:
                for name, value in self._observing_func.items():
                    every_n_sec = value[1]
                    if time % every_n_sec == 0:
                        self._observing_locked = True
                        value[0]()
                        self._observing_locked = False

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
    def always_available_public_functions(self) -> Tuple[CmdStruct]:
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
            error_logger(self, self.add_to_executor, e)
            return False

    def _connect_pyqtslot_signal(self, pyqtslot):
        # Pyqt slot and signal are connected
        self.signal.connect(pyqtslot)
        self.pyqtsignal_connected = True

    @abstractmethod
    def description(self) -> Dict[str, Any]:
        """
        return description of device, configuration depends on device type: stpmtr, detector, etc.
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

    @property
    def get_main_device_parameters(self) -> Dict[str, Union[str, List[str]]]:
        return self.get_settings('Parameters_Main_Devices')

    @property
    def get_parameters(self) -> Dict[str, Union[str, List[str]]]:
        return self.get_settings('Parameters_Controller')

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
            raise DeviceError(self, f"_get_list_db: field {what} or section {from_section} is absent in the DB")
        except (TypeError, SyntaxError):
            raise DeviceError(self, f"_get_list_db: list param should be = (x1, x2); (x3, x4); or X1; X2;...")

    def generate_msg(self, msg_com: Union[MsgComInt, MsgComExt], **kwargs) -> Union[MessageExt, MessageInt, None]:
        """
        This function is dedicated to generate Messages for some device
        :param msg_com:
        :param kwargs: could be any, depends on the message definition
        :return: Union[MessageExt, MessageInt, None]
        """
        def gen_msg(self, msg_com: Union[MsgComInt, MsgComExt], **kwargs) -> Union[MessageExt, MessageInt, None]:
            try:
                if isinstance(msg_com, MsgComExt):
                    message_info: MessageInfoExt = msg_com.value
                    if not set(message_info.must_have_param).issubset(set(kwargs.keys())):
                        error_logger(self, self.generate_msg, f'Not all required parameters are given for {msg_com} '
                                                              f'such as {message_info.must_have_param}, but instead '
                                                              f'{kwargs.keys()}')
                        raise DeviceError(self, f'Not all parameters are passed to device.generate_msg')
                if msg_com is MsgComExt.AVAILABLE_SERVICES:
                    info = AvailableServices(available_services=kwargs['available_services'])
                elif msg_com is MsgComExt.DO_IT:
                    info = kwargs['func_input']
                elif msg_com is MsgComExt.DONE_IT:
                    info = kwargs['func_output']
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
                    info = MsgError(comments=kwargs['comments'])
                elif msg_com is MsgComInt.DEVICE_INFO_INT:
                    info = DeviceInfoInt(active_connections=self.active_connections(),
                                         available_public_functions=self.available_public_functions(),
                                         device_id=self.id,
                                         device_status=self.controller_status, device_description=self.description(),
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
                    try:
                        server_public_key = self.connections[self.server_id].device_public_key
                        pub_key = self.messenger.public_key
                        device_public_key_crypted = self.messenger.encrypt_with_public(pub_key,
                                                                                       server_public_key)
                    except KeyError:
                        device_public_key_crypted = self.messenger.public_key
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
                        forward_to = ''
                        forwarded_from = ''
                    elif msg_com.msg_type is MsgType.DIRECTED:
                        try:
                            reply_to = kwargs['reply_to']
                        except KeyError:
                            reply_to = ''
                        try:
                            forward_to = kwargs['forward_to']
                        except KeyError:
                            forward_to = ''
                        try:
                            forwarded_from = kwargs['forwarded_from']
                        except KeyError:
                            forwarded_from = ''
                        receiver_id = kwargs['receiver_id']

                    # Sometimes heavy outputs are not crypted, to make everything work faster
                    if hasattr(info, 'crypted'):
                        crypted = getattr(info, 'crypted')
                    else:
                        crypted = msg_com.msg_crypted

                    return MessageExt(com=msg_com.msg_name, crypted=crypted, info=info, receiver_id=receiver_id,
                                      reply_to=reply_to, sender_id=self.messenger.id, forward_to=forward_to,
                                      forwarded_from=forwarded_from)
                else:
                    return MessageInt(com=msg_com.msg_name, info=info, sender_id=self.messenger.id)
        if not (isinstance(msg_com, MsgComExt) or isinstance(msg_com, MsgComInt)):
            error_logger(self, self.generate_msg, f'Wrong msg_com is passed, not MsgCom')
            return None
        else:
            return gen_msg(self, msg_com, **kwargs)

    def execute_com(self, msg: MessageExt):
        error = False
        com: str = msg.info.com
        input: FuncInput = msg.info
        do = False
        if com in self.available_public_functions_names and self.ctrl_status.active:
            do = True
        elif com in self.always_available_public_functions_names:
            do = True
        elif com not in self.available_public_functions_names:
            error = True
            comments = f'com: {com} is not available for Service {self.id}. See {self.available_public_functions()}.'
        elif not self.ctrl_status.active:
            error = True
            comments = f'{self.id} is not active. Cannot execute command {com}.'
        if do:
            f = getattr(self, com)
            func_input_type = signature(f).parameters['func_input'].annotation
            if func_input_type == type(input):
                try:
                    result: FuncOutput = f(input)
                    if msg.forwarded_from != '':
                        forward_to = msg.forwarded_from
                    else:
                        forward_to = ''
                    msg_r = self.generate_msg(msg_com=MsgComExt.DONE_IT, receiver_id=msg.sender_id, func_output=result,
                                              reply_to=msg.id, forward_to=forward_to)
                except Exception as e:  # TODO: replace Exception
                    error_logger(self, self.execute_com, e)
                    error = True
                    comments = str(e)
            else:
                error = True
                comments = f'Device {self.id} function: execute_com: Input type: {type(input)} do not match to ' \
                           f'func_input type : {func_input_type}'
        if error:
            if msg.forwarded_from != '':
                forward_to = msg.forwarded_from
            else:
                forward_to = ''
            comments = join_smart_comments(comments, str(msg.short()))
            msg_r = self.generate_msg(msg_com=MsgComExt.ERROR, comments=comments, receiver_id=msg.sender_id,
                                      forward_to=forward_to, reply_to=msg.id)
            error_logger(self, self.execute_com, msg_r)
        self.send_msg_externally(msg_r)

    @staticmethod
    def exec_mes_every_n_sec(f: Callable, delay=5, n_max=10, specific={'with_return': False}) -> None:
        i = 0
        if delay > 5:
            delay = 5
        from time import sleep
        flag = True
        while flag and i < n_max:
            i += 1
            sleep(delay)
            if specific['with_return']:
                flag = f(**specific)
            else:
                f()

    def pause(self):
        self.thinker.pause()
        self.messenger.pause()
        self.ctrl_status.messaging_paused = True
        self.send_status_pyqt()

    @property
    def public_sockets(self):
        return self.messenger.public_sockets

    def unpause(self):
        self.messenger.unpause()
        self.thinker.unpause()
        self.ctrl_status.messaging_paused = False
        self.send_status_pyqt()

    def start(self):
        self._start_messaging()

    def stop(self):
        self._observing_FLAG = False
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
        self.thinker.flush_tasks()
        for device_id, connection in self.connections.items():
            if isinstance(self, Server):
                stop_msg = self.generate_msg(msg_com=MsgComExt.SHUTDOWN, receiver_id=device_id,
                                             reason='normal_shutdown')
            else:
                if device_id == self.server_id:
                    stop_msg = self.generate_msg(msg_com=MsgComExt.SHUTDOWN, receiver_id=device_id,
                                                 reason='normal_shutdown')
                else:
                    stop_msg = self.generate_msg(msg_com=MsgComExt.SHUTDOWN, receiver_id=self.server_id,
                                                 forward_to=device_id, reason='normal_shutdown')
            self.thinker.add_task_out(stop_msg)
        sleep(0.1)
        self.thinker.pause()
        self.messenger.pause()
        self.thinker.stop()
        self.messenger.stop()
        self.send_status_pyqt()
        self.ctrl_status.messaging_paused = False
        self.ctrl_status.messaging_on = False
        info_msg(self, 'STOPPED')

    @abstractmethod
    def send_status_pyqt(self):
        pass

    def send_msg_externally(self, msg: MessageExt):
        self.thinker.add_task_out(msg)

    def update_config(self, message: str):
        # TODO: realize
        self.logger.info('Config is updated: ' + message)


class Server(Device):
    ALIVE = CmdStruct(FuncAliveInput, FuncAliveOutput)
    GET_AVAILABLE_SERVICES = CmdStruct(FuncAvailableServicesInput, FuncAvailableServicesOutput)

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
        self.device_status = DeviceControllerStatus(active=True, power=True)  # Power is always ON for server and it is active

    def are_you_alive(self, func_input: FuncAliveInput) -> FuncAliveOutput:
        event = self.thinker.events['heartbeat']
        return FuncAliveOutput(comments='', func_success=True, device_id=self.id, event_id=event.id, event_n=event.n)

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
        """Returns dict of available services {DeviceID: name}"""
        return FuncAvailableServicesOutput(comments='', func_success=True,  device_id=self.id,
                                           device_available_services=self.available_services)

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return self.always_available_public_functions()

    def always_available_public_functions(self) -> Tuple[CmdStruct]:
        return ([Server.ALIVE, Server.GET_AVAILABLE_SERVICES])

    def description(self) -> ServerDescription:
        parameters = self.get_parameters
        return ServerDescription(info=parameters['info'], GUI_title=parameters['title'])

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
        # Every Client gets its parameters from SuperUser at this moment, thus its id changes to unique by adding ::
        id = kwargs['id']
        from random import randint
        kwargs['id'] = f'{id}::{randint(0, 10)}::{randint(0,10)}'
        super().__init__(**kwargs)
        self.server_id = self.get_settings('General')['server_id']
        self.device_status = DeviceControllerStatus(active=True, power=True)  # Power is always ON for client and it is active

    @property
    def available_services(self) -> Dict[DeviceId, str]:
        pass

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return ()

    def always_available_public_functions(self) -> Tuple[CmdStruct]:
        return ()

    def activate(self, flag: bool):
        """Client is always active"""
        self.logger.info("""Client is always active""")

    def description(self) -> ClientDescription:
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
    ACTIVATE_DEVICE = CmdStruct(FuncActivateDeviceInput, FuncActivateDeviceOutput)
    ACTIVATE = CmdStruct(FuncActivateInput, FuncActivateOutput)
    GET_CONTROLLER_STATE = CmdStruct(FuncGetControllerStateInput, FuncGetControllerStateOutput)
    SET_CONTROLLER_STATE = CmdStruct(None, None)  # TODO: finalize
    SERVICE_INFO = CmdStruct(FuncServiceInfoInput, FuncServiceInfoOutput)
    POWER = CmdStruct(FuncPowerInput, FuncPowerOutput)

    # TODO: add loop to observed controller activity, maybe connection is lost, or something like this
    # TODO: Service and Client are basically the same thing. So they must be merged somehow
    def __init__(self, **kwargs):
        from communication.messaging.messengers import ServiceMessenger
        if 'thinker_cls' in kwargs:
            cls_parts = {'Thinker': kwargs['thinker_cls'],
                         'Messenger': ServiceMessenger}
        else:
            raise DeviceError(self, 'Thinker cls was not passed to Device factory')
        kwargs['cls_parts'] = cls_parts
        if 'db_command' not in kwargs:
            raise DeviceError(self, 'DB_command is not defined.')
        kwargs['type'] = DeviceType.SERVICE
        super().__init__(**kwargs)
        self.server_id: DeviceId = self.get_settings('General')['server_id']  # must be here
        self._hardware_device_dataclass = kwargs['hardware_device_dataclass']
        self._hardware_devices: Dict[Union[int, str], HardwareDevice] = HardwareDeviceDict()
        self.power_settings: PowerSettings = PowerSettings()

    @property
    def available_services(self) -> Dict[DeviceId, str]:
        pass

    def activate(self, func_input: FuncActivateInput) -> FuncActivateOutput:
        flag = func_input.flag
        res, comments = self._check_if_active()
        if res ^ flag:  # res XOR Flag
            info_msg(self, 'INFO', f'Func "activate" is called: {func_input}.')
            if flag:
                res, comments = self._connect(flag)  # guarantees that parameters could be read from controller
                if res:  # parameters should be set from hardware controller if possible
                    res, comments = self._set_parameters_main_devices(extra_func=[self._set_parameters_after_connect])  # This must be realized for all controllers
                    if res:
                        self.ctrl_status.active = True
            else:
                res, comments = self._connect(flag)
                if res:
                    self.ctrl_status.active = flag
        comments = f'Func "activate" is accomplished with success: {res}. State of controller is ' \
                   f'{self.ctrl_status.active}. {comments}'
        return FuncActivateOutput(comments=comments, controller_status=self.ctrl_status, func_success=res)

    def activation(self):
        sleep(1)
        res: FuncActivateOutput = self.activate(func_input=FuncActivateInput(flag=True))
        if res.func_success:
            for device in self.hardware_devices.values():
                self.activate_device(func_input=FuncActivateDeviceInput(device_id=device.device_id_seq, flag=1))

    def activate_device(self, func_input: FuncActivateDeviceInput) -> FuncActivateDeviceOutput:
        device_id = func_input.device_id
        flag = func_input.flag
        res, comments = self._check_device_range(device_id)
        info_msg(self, 'INFO', f'Func "activate_device" is called: {func_input}.')
        if res:
            device = self.hardware_devices[device_id]
            res, comments = self.change_device_status(device_id, flag)
        comments = f'Func "activate_device" is accomplished with success: {res}. {comments}'
        info_msg(self, 'INFO', comments)
        return FuncActivateDeviceOutput(device=device, comments=comments, func_success=res)

    @abstractmethod
    def available_public_functions(self) -> Tuple[CmdStruct]:
        return self.always_available_public_functions()

    def always_available_public_functions(self) -> Tuple[CmdStruct]:
        return (Service.ACTIVATE, Service.ACTIVATE_DEVICE, Service.GET_CONTROLLER_STATE, Service.SERVICE_INFO,
                Service.POWER)

    def _check_device_range(self, device_id):
        if device_id in self._hardware_devices:
            return True, ''
        else:
            return False, f'Device id={device_id} is out of range={self._hardware_devices.all_keys()}.'

    def _check_if_active(self) -> Tuple[bool, str]:
        return self.ctrl_status.active, ''

    def _check_device(self, device_id: int) -> Tuple[bool, str]:
        res, comments = self._check_device_range(device_id)
        if res:
            return self._check_device_active(device_id)
        else:
            return res, comments

    def _check_device_active(self, device_id: Union[int, str]) -> Tuple[bool, str]:
        if self.hardware_devices[device_id].status:
            return True, ''
        else:
            return False, f'Device id={device_id}, name={self.hardware_devices[device_id].friendly_name} is not active.'

    def _check_controller_activity(self):
        if self.ctrl_status.active:
            return True, ''
        else:
            return False, f'Controller is not active. Power is {self.ctrl_status.power}.'

    def change_device_status(self, device_id: int, flag: int, force=False) -> Tuple[bool, str]:
        res, comments = self._check_device_range(device_id)
        if res:
            res, comments = self._check_status_flag(flag)
        if res:
            device = self._hardware_devices[device_id]
            if device.status != flag:
                res, comments = self._change_device_status_local(device, flag, force)
            else:
                res, comments = True, f'{device.friendly_name} is already set to {flag}.'
        return res, comments

    @abstractmethod
    def _change_device_status_local(self, device: HardwareDevice, flag: int, force=False) -> Tuple[bool, str]:
        return False, ''

    @staticmethod
    @abstractmethod
    def _check_status_flag(flag: int):
        pass

    def _check_if_connected(self) -> Tuple[bool, str]:
        """
        In real devices should ask hardware controller
        :return:
        """
        return self.ctrl_status.connected, ''

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        if self.ctrl_status.power:
            if flag:
                res, comments = self._form_devices_list()
            else:
                res, comments = self._release_hardware()
            self.ctrl_status.connected = flag
        else:
            res, comments = False, f'Power is off, cannot not call "connect(flag={flag})" controller.'
        return res, comments

    def _get_hardware_devices_ids_db(self):
        try:
            ids: List[Union[int, str]] = []
            for exp in self.get_main_device_parameters['ids'].replace(" ", "").split(';'):
                try:
                    val = eval(exp)
                except (SyntaxError, NameError, TypeError):
                    val = exp
                if val:
                    ids.append(val)
            if len(ids) != self._hardware_devices_number:
                raise DeviceError(self, f"Number of devices {len(ids)} is not equal to "
                                        f"'hardware_devices_number={self._hardware_devices_number}'.")
            return ids
        except KeyError:
            raise DeviceError(self, text="Hardware devices 'ids' could not be set, field is absent in the DB.")

    def description(self) -> ServiceDescription:
        """
        Description with important parameters
        :return: ServiceDescription with parameters essential for understanding what this device is used for
        """
        try:
            return ServiceDescription(hardware_devices=self.hardware_devices, info=self.get_parameters['info'],
                                      GUI_title=self.get_parameters['title'], power_settings=self.power_settings,
                                      class_name=self.__class__.__name__)
        except (KeyError, DeviceError) as e:
            return DeviceError(self, f'Could not find description of the controller: {e}. Check the DB.')

    @abstractmethod
    def _form_devices_list(self) -> Tuple[bool, str]:
        pass

    def get_controller_state(self, func_input: FuncGetControllerStateInput) -> FuncGetControllerStateOutput:
        return FuncGetControllerStateOutput(devices_hardware=self.hardware_devices, func_success=True, comments='',
                                            controller_status=self.ctrl_status)

    @abstractmethod
    def _get_number_hardware_devices(self) -> int:
        return self._hardware_devices_number

    def _get_number_hardware_devices_db(self):
        try:
            return int(self.get_main_device_parameters['devices_number'])
        except KeyError:
            raise DeviceError(self, text="Number of devices for controller could not be set, number field is absent "
                                         "in the database")
        except (ValueError, SyntaxError):
            raise DeviceError(self, text=f"Check 'number' field in the database for {self.id}, the line "
                                         f"'number = value' must be present")

    @property
    @abstractmethod
    def hardware_devices(self) -> Dict[int, HardwareDevice]:
        return self._hardware_devices

    @property
    @abstractmethod
    def hardware_devices_essentials(self) -> Dict[int, HardwareDeviceEssentials]:
        return {device.device_id_seq: device.short() for device in self.hardware_devices.values()}

    def power(self, func_input: FuncPowerInput) -> FuncPowerOutput:
        # TODO: to be realized in metal someday
        flag = func_input.flag
        info_msg(self, 'INFO', f'Func "power" is called: {func_input}.')
        if self.ctrl_status.power ^ flag:  # XOR
            if not flag and self.ctrl_status.active:
                res, comments = False, f'Power is {self.ctrl_status.power}. Cannot switch power off ' \
                                       f'when device is activated.'
            else:
                if not self.power_settings.controller_id:
                    self.ctrl_status.power = flag
                    res, comments = True, f'Power is {self.ctrl_status.power}. Device does not require power.'
                elif self.power_settings.controller_id == 'manually':
                    self.ctrl_status.power = flag
                    res, comments = True, f'Power is {self.ctrl_status.power}. But remember, ' \
                                          f'that user must switch power manually...'
                else:
                    from devices.service_devices.pdu.pdu_dataclass import FuncSetPDUStateInput
                    msg = self.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.server_id,
                                            forward_to=self.power_settings.controller_id,
                                            func_input=FuncSetPDUStateInput(pdu_id=self.power_settings.pdu_id,
                                                                            pdu_output_id=self.power_settings.output_id,
                                                                            output=int(flag)))
                    self.send_msg_externally(msg)
                    res, comments = True, ''
        else:
            res, comments = True, ''
        comments = f'Func "power" is accomplished with success: {res}. State of controller is ' \
                   f'{self.ctrl_status.power}. {comments}'
        info_msg(self, 'INFO', comments)
        return FuncPowerOutput(comments=comments, controller_status=self.ctrl_status, func_success=res)

    @abstractmethod
    def _release_hardware(self) -> Tuple[bool, str]:
        return True, ''

    def _set_ids_devices(self):
        if not self.ctrl_status.connected:
            ids = self._get_hardware_devices_ids_db()
            for id_a, seq_id in zip(ids, range(1, self._hardware_devices_number + 1)):
                self._hardware_devices[seq_id] = self._hardware_device_dataclass(device_id=id_a, device_id_seq=seq_id)

    def _set_parameters_main_devices(self, parameters: List[Tuple[str, Any]] = None, extra_func: List[Callable] = None) -> Tuple[bool, str]:
        try:
            self._set_number_hardware_devices()
            self._set_ids_devices()  # Ids must be set first, just after number of hardware devices

            if parameters:
                for name_to_set, parameter, parameter_type in parameters:
                    self._set_parameter_device_by_name(name_to_set, parameter, parameter_type)

            res, comments = [], ''

            if extra_func:
                for func in extra_func:
                    r, com = func()
                    res.append(r)
                    comments = join_smart_comments(comments, com)

            res = all(res)
        except (DeviceError, Exception) as e:
            error_logger(self, self._set_parameters, e)
            res, comments = False, str(e)
        finally:
            if self.ctrl_status.connected and res:
                self._parameters_set_hardware = True
            return res, comments

    def _set_parameter_device_by_name(self, name_set: str, parameter_name: str, parameter_type: type):
        """

        :param name_set: how the parameter is called withing dataclass of the hardware device
        :param parameter_name: parameter field in the DB
        :param parameter_type: str, int, etc...
        :return: None
        """
        try:
            parameter_value = self.get_main_device_parameters[parameter_name]
            try:
                parameter_value = eval(parameter_value)
            except (SyntaxError, NameError, TypeError) as e:
                raise DeviceError(self, f'Parameter {parameter_name} could not be set: {e}')
            if not isinstance(parameter_value, dict):
                raise DeviceError(self, f'Parameter {parameter_name} could not be set, field is not python-like dict.')
            else:
                if len(parameter_value) != self._hardware_devices_number:
                    raise DeviceError(self, f'Parameter {parameter_name} could not be set: Number of parameters in dict '
                                            f'does not equal to number of hardware devices.')
                else:
                    for device_id, param_value in parameter_value.items():
                        try:
                            hardware_device = self._hardware_devices[device_id]
                            setattr(hardware_device, name_set, param_value)
                        except KeyError as e:
                            raise DeviceError(self, f'Parameter {parameter_name} could not be set: '
                                                    f'Wrong device_id {device_id} was passed. Check the DB.')

        except KeyError:
            raise DeviceError(self, f'Parameter {parameter_name} could not be set, it is absent in the DB.')

    @abstractmethod
    def _set_parameters_after_connect(self) -> Tuple[bool, str]:
        return True, ''

    def _set_power_settings(self) -> Tuple[bool, str]:
        try:
            power_param = eval(self.get_parameters['power_controller_parameters'])
            self.power_settings = PowerSettings(*power_param)
            return True, ''
        except (SyntaxError, ValueError) as e:
            error_logger(self, self._set_power_settings, e)
            return False, f'During setting power controller setting error occurred: {e}.'

    def send_status_pyqt(self):
        pass

    def service_info(self, func_input: FuncServiceInfoInput) -> FuncServiceInfoOutput:
        service_info = ControllerInfoExt(device_id=self.id, device_description=self.description(),
                                         controller_status=self.ctrl_status)
        return FuncServiceInfoOutput(comments='', func_success=True, device_id=self.id, service_info=service_info)

    def _set_number_hardware_devices(self):
        if self.ctrl_status.connected:
            n = self._get_number_hardware_devices()
            if n != self._hardware_devices_number:
                raise DeviceError(self, f'Number of hardware of device during activation of controller is not equal to '
                                        f'those indicated in DB.')
        else:
            self._hardware_devices_number = self._get_number_hardware_devices_db()

    def stop(self):
        self.activate(FuncActivateInput(False))
        super().stop()


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
                    module_devices = import_module('devices.virtual_devices')
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
