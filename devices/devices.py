import logging
import sqlite3 as sq3
import sys
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from inspect import signature, isclass
from pathlib import Path
from time import sleep
from typing import Union, Dict, List, Tuple, Any, Callable

from PyQt5.QtCore import QObject, pyqtSignal

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(Path(__file__).resolve().parents[1]))
from database.tools import db_create_connection, db_execute_select, db_close_conn
from communication.interfaces import ThinkerInter, MessengerInter
from communication.messaging.message_utils import MsgGenerator
from errors.messaging_errors import MessengerError
from errors.myexceptions import DeviceError
from devices.interfaces import DeciderInter, ExecutorInter, DeviceInter
from utilities.configurations import configurationSD
from utilities.data.datastructures.mes_independent.devices_dataclass import *
from utilities.data.datastructures.mes_independent import CmdStruct
from utilities.data.datastructures.mes_dependent.general import Connection
from utilities.data.datastructures.mes_dependent.dicts import Connections_Dict
from utilities.data.messages import Message, DoIt
from utilities.myfunc import info_msg, unique_id
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

    signal = pyqtSignal(Message)

    def __init__(self,
                 name: str,
                 db_path: Path,
                 cls_parts: Dict[str, Union[ThinkerInter, MessengerInter, DeciderInter, ExecutorInter]],
                 parent: QObject = None,
                 DB_command: str = '',
                 logger_new=True,
                 test=False,
                 **kwargs):
        super().__init__()
        self.test = test
        self.available_public_functions_names = list(cmd.name for cmd in self.available_public_functions())
        self._main_executor = ThreadPoolExecutor(max_workers=100)
        Device.n_instance += 1
        if logger_new:
            self.logger = initialize_logger(app_folder / 'LOG', file_name=__name__ + '.' + self.__class__.__name__)
            if test:
                self.logger.setLevel(logging.ERROR)
                #self.logger.disabled = True
        else:
            self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        if 'id' not in kwargs:
            self.id = f'{name}:{unique_id(name)}'
        else:
            self.id = kwargs['id']

        self.name: str = name
        self.parent: QObject = parent

        self.db_path = db_path
        self.config = configurationSD(self)

        self.connections: Dict[str, Connection] = Connections_Dict()

        self.cls_parts: Dict[str, Union[ThinkerInter, MessengerInter, DeciderInter, ExecutorInter]] = cls_parts

        self.device_status: DeviceStatus = DeviceStatus(*[False] * 5)

        try:
            assert len(self.cls_parts) == 3
            for key, item in self.cls_parts.items():
                assert key in ['Messenger', 'Thinker', 'Decider']
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
            res, comments = db_execute_select(db_conn, DB_command)
            db_close_conn(db_conn)
            self.config.add_config(self.name, config_text=res)

            from communication.messaging.messengers import Messenger
            from communication.logic.thinkers_logic import Thinker
            from devices.soft.deciders import Decider

            if 'pub_option' not in kwargs:
                kwargs['pub_option'] = True

            self.messenger: Messenger = self.cls_parts['Messenger'](name=self.name,
                                                                    addresses=self.get_addresses(),
                                                                    parent=self,
                                                                    pub_option=kwargs['pub_option'])
            self.thinker: Thinker = self.cls_parts['Thinker'](parent=self)
            self.decider: Decider = self.cls_parts['Decider'](parent=self)
        except (sq3.Error, KeyError, MessengerError, Exception) as e:
            self.logger.error(e)
            raise DeviceError(str(e))

        info_msg(self, 'CREATED')

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
        except Exception as e:
            self.logger.error(e)
            return False

    def _connect_pyqtslot_signal(self, pyqtslot):
        # Pyqt slot and signal are connected
        self.signal.connect(pyqtslot)
        self.pyqtsignal_connected = True
        self.logger.info(f'pyqtsignal is set to True')

    def decide_on_msg(self, msg: Message) -> None:
        # TODO : realise logic
        decision = self.decider.decide(msg)
        if decision.allowed:
            self.thinker.add_task_in(msg)
        else:
            pass  # should be send back or whereever

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

    def execute_com(self, msg: Message):
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

    def info(self) -> Dict[str, Union[DeviceStatus, Any]]:
        from collections import OrderedDict as od
        info = od()
        info['device_status'] = self.device_status
        info['messenger_status'] = self.messenger.info()
        info['thinker_status'] = self.thinker.info()
        info['decider_status'] = self.decider.info()
        return info

    @abstractmethod
    def messenger_settings(self):
        pass

    def pause(self):
        self.thinker.pause()
        self.messenger.pause()
        self.device_status.messaging_paused = True
        self.send_status_pyqt()

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
        self.thinker.start()
        self.messenger_settings()
        self.messenger.start()
        info_msg(self, 'STARTED')
        self.send_status_pyqt()


    def _stop_messaging(self):
        """Stop messaging part of Device"""
        info_msg(self, 'STOPPING')
        stop_msg = MsgGenerator.shutdown_info(device=self, reason='normal shutdown')
        self.messenger.send_msg(stop_msg)
        sleep(0.1)
        self.thinker.pause()
        self.messenger.pause()
        self.thinker.stop()
        self.messenger.stop()
        self.send_status_pyqt()
        self.device_status.messaging_paused = False
        self.device_status.messaging_on = False
        info_msg(self, 'STOPPED')


    def send_status_pyqt(self, com=''):
        # TODO: rewrite so it is unique for every type of device. make it @abstractmethod
        if self.pyqtsignal_connected:
            if com == 'status_server_info_full':
                msg = MsgGenerator.status_server_info_full(device=self)
            elif com == 'status_server_info':
                msg = MsgGenerator.status_server_info(device=self)
            elif com == 'status_client_info':
                msg = MsgGenerator.status_client_info(device=self)
            else:
                self.logger.error(f'send_status_pyqt com {com} is not known')
                msg = None
            if msg:
                self.signal.emit(msg)
        else:
            self.logger.info(f'pyqtsignal_connected is {self.pyqtsignal_connected}, the signal cannot be emitted')

    def send_msg_externally(self, msg: Message):
        self.messenger.add_msg_out(msg)

    def update_config(self, message: str):
        # TODO: realize
        self.logger.info('Config is updated: ' + message)

    #def __del__(self):
        #self.logger.info(f"Instance of class {self.__class__.__name__}: {self.name} is deleted")
        #del self


class Server(Device):
    AVAILABLE_SERVICES = CmdStruct('available_services', FuncAvailableServicesInput, FuncAvailableServicesOutput)
    MAKE_CONNECTION = CmdStruct('make_connection', None, None)

    def __init__(self, **kwargs):
        from communication.logic.thinkers_logic import ServerCmdLogic
        from communication.messaging.messengers import ServerMessenger
        from devices.soft.deciders import ServerDecider
        cls_parts = {'Thinker': ServerCmdLogic,
                     'Decider': ServerDecider,
                     'Messenger': ServerMessenger}
        kwargs['cls_parts'] = cls_parts
        if 'DB_command' not in kwargs:
            kwargs['DB_command'] = "SELECT parameters from SERVER_settings where name = 'default'"
        self.services_available = {}
        self.type = 'server'
        # initialize_logger(app_folder / 'bin' / 'LOG', file_name="Server")
        super().__init__(**kwargs)
        self.device_status = DeviceStatus(active=True, power=True)  # Power is always ON for server and it is active

    @property
    def services_running(self) -> Dict[str, str]:
        """Returns dict of running services {device_id: name}"""
        services_running = {}
        for device_id, connection in self.connections.items():
            info = connection.device_info
            if info.type == 'service':
                services_running[device_id] = info.name
        return services_running

    @property
    def clients_running(self) -> Dict[str, str]:
        """Returns dict of running clients {device_id: name}"""
        clients_running = {}
        for device_id, connection in self.connections.items():
            info = connection.device_info
            if info.type == 'client':
                clients_running[device_id] = info.name
        return clients_running

    def activate(self, flag: bool):
        """Server is always active"""
        self.logger.info("""Server is always active""")

    def available_services(self, func_input: FuncAvailableServicesInput) -> FuncAvailableServicesOutput:
        return FuncAvailableServicesOutput(comments='', func_success=True,  running_services=self.services_running,
                                           all_services={})

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return (Server.AVAILABLE_SERVICES, Server.MAKE_CONNECTION)

    def description(self) -> Dict[str, Any]:
        # TODO: realize
        return {}

    def messenger_settings(self):
        # FIXME:...
        pass

    def start(self):
        super().start()

    def send_status_pyqt(self, com=''):
        super().send_status_pyqt(com='status_server_info_full')

    def set_default(self):
        pass


class Client(Device):
    """
    class Client communicates with Server to get access to Service it is bound to
    through service_devices determined within the model of PyQT application devoted to this task.
    """

    def __init__(self, **kwargs):
        from communication.messaging.messengers import ClientMessenger
        from devices.soft.deciders import ClientDecider

        if 'thinker_cls' in kwargs:
            cls_parts = {'Thinker': kwargs['thinker_cls'],
                         'Decider': ClientDecider,
                         'Messenger': ClientMessenger}
        else:
            raise Exception('Thinker cls was not passed to Device factory')

        kwargs['cls_parts'] = cls_parts
        self.type = 'client'
        # initialize_logger(app_folder / 'bin' / 'LOG', file_name=kwargs['name'])
        super().__init__(**kwargs)
        self.server_id = self.get_settings('General')['server_id']
        self.device_status = DeviceStatus(active=True, power=True)  # Power is always ON for client and it is active

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return ()

    def activate(self, flag: bool):
        """Server is always active"""
        self.logger.info("""Client is always active""")

    def description(self) -> Dict[str, Any]:
        # TODO: add functionality
        pass

    def execute_com(self, msg: Message):
        pass

    def messenger_settings(self):
        for adr in self.messenger.addresses['server_publisher']:
            self.messenger.subscribe_sub(address=adr)

    def start(self):
        super().start()

    def send_status_pyqt(self, com=''):
        super().send_status_pyqt(com='status_client_info')

    def set_default(self):
        pass


class Service(Device):
    ACTIVATE = CmdStruct('activate', FuncActivateInput, FuncActivateOutput)
    GET_CONTROLLER_STATE = CmdStruct('get_controller_state', FuncGetControllerStateInput, FuncGetControllerStateOutput)
    POWER = CmdStruct('power', FuncPowerInput, FuncPowerOutput)

    # TODO: Service and Client are basically the same thing. So they must be merged somehow
    def __init__(self, **kwargs):
        from communication.messaging.messengers import ServiceMessenger
        from devices.soft.deciders import ServiceDecider
        if 'thinker_cls' in kwargs:
            cls_parts = {'Thinker': kwargs['thinker_cls'],
                         'Decider': ServiceDecider,
                         'Messenger': ServiceMessenger}
        else:
            raise Exception('Thinker cls was not passed to Device factory')

        kwargs['cls_parts'] = cls_parts
        if 'DB_command' not in kwargs:
            raise Exception('DB_command_type is not determined')

        self.type = 'service'
        # initialize_logger(app_folder / 'bin' / 'LOG', file_name=kwargs['name'])
        super().__init__(**kwargs)
        self.server_id = self.get_settings('General')['server_id']

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
    def description(self):
        pass

    @abstractmethod
    def get_controller_state(self, func_input: FuncGetControllerStateInput) -> FuncGetControllerStateOutput:
        pass

    def messenger_settings(self):
        for adr in self.messenger.addresses['server_publisher']:
            try:
                self.messenger.subscribe_sub(address=adr)
            except Exception as e:
                a = e
                print(e)

    def send_status_pyqt(self, com=''):
        super().send_status_pyqt(com='status_service_info')

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
        return FuncPowerOutput(comments=comments, device_status=self.device_status, func_success=success)


class DeviceFactory:
    @staticmethod
    def make_device(**kwargs):  #TODO: redifine kwargs
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
                elif project_type == 'Service':
                    module_devices = import_module('devices.service_devices')
                else:
                    raise Exception(f'Project type: {project_type} is not known')

                cls = getattr(module_devices, device_name)
                device_name_split = device_name.split('_')[0]
                thinker_class = getattr(module_comm_thinkers, f'{device_name_split}{project_type}CmdLogic')
                kwargs['name'] = device_name
                kwargs['thinker_cls'] = thinker_class
                kwargs['DB_command'] = f'SELECT parameters from DEVICES_settings where device_id = "{device_id}"'
                kwargs['id'] = device_id
                if issubclass(cls, Device):
                    return cls(**kwargs)
            else:
                raise BaseException('DeviceFactory Crash: device_id or db_path were not passed')
