import logging
import sys
import sqlite3 as sq3
from pathlib import Path
from abc import abstractmethod
from pathlib import Path
from time import sleep
from typing import Union, Dict, List, Tuple, Any, Callable
from inspect import signature, isclass
from PyQt5.QtCore import QObject, pyqtSignal
from concurrent.futures import ThreadPoolExecutor

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(Path(__file__).resolve().parents[1]))

from DB.tools import create_connectionDB, executeDBcomm, close_connDB
from communication.interfaces import ThinkerInter, MessengerInter
from communication.messaging.message_utils import MsgGenerator
from errors.messaging_errors import MessengerError
from errors.myexceptions import DeviceError
from devices.interfaces import DeciderInter, ExecutorInter, DeviceInter
from utilities.configurations import configurationSD
from utilities.data.datastructures.mes_independent import DeviceStatus
from utilities.data.datastructures.mes_dependent import Connection
from utilities.data.datastructures.dicts import Connections_Dict
from utilities.data.messages import Message
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
                 **kwargs):
        super().__init__()
        self._main_executor = ThreadPoolExecutor(max_workers=100)
        Device.n_instance += 1
        if logger_new:
            self.logger = initialize_logger(app_folder / 'LOG', file_name=__name__ + '.' + self.__class__.__name__)
        else:
            self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

        if 'id' not in kwargs:
            self.id = f'{name}:{unique_id(name)}'
        else:
            self.id = kwargs['id']

        self.name = f'{name}:{Device.n_instance}'
        self.parent: QObject = parent

        self.db_path = db_path
        self.config = configurationSD(self)

        self.connections: Dict[str, Connection] = Connections_Dict()

        self.cls_parts: Dict[str, Union[ThinkerInter, MessengerInter, DeciderInter, ExecutorInter]] = cls_parts

        self.device_status: DeviceStatus = DeviceStatus(*[False] * 4)

        try:
            assert len(self.cls_parts) == 3
            for key, item in self.cls_parts.items():
                assert key in ['Messenger', 'Thinker', 'Decider']
                assert isclass(item)
        except AssertionError as e:
            self.logger.error(e)
            raise e

        try:
            self.signal.connect(kwargs['pyqtslot'])
            self.pyqtsignal_connected = True
            self.logger.info(f'pyqtsignal is set to True')
        except KeyError as e:
            self.pyqtsignal_connected = False
            self.logger.info(f'pyqtsignal is set to False')

        # config is set here
        try:
            self.db_conn, self.cur = create_connectionDB(self.db_path)
            res = executeDBcomm(self.cur, DB_command)
            close_connDB(self.db_conn)
            self.config.add_config(self.name, config_text=res[0])

            from communication.messaging.messengers import Messenger
            from communication.logic.thinkers import Thinker
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
    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        pass

    @abstractmethod
    def activate(self, flag: bool):
        pass

    @abstractmethod
    def description(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def messenger_settings(self):
        pass

    @abstractmethod
    def power(self, flag: bool):
        pass

    def add_to_executor(self, func, **kwargs) -> bool:
        # used for slow methods and functions
        try:
            self._main_executor.submit(func, **kwargs)
            return True
        except:
            return False

<<<<<<< HEAD
    def get_general_settings(self) -> Dict[str, Union[str, List[str]]]:
        return self.config.config_to_dict(self.name)['General']

    def get_addresses(self) -> Dict[str, Union[str, List[str]]]:
        res = self.config.config_to_dict(self.name)['Addresses']
        return res
=======
    def get_settings(self, name: str) -> Dict[str, Union[str, List[str]]]:
        try:
            return self.config.config_to_dict(self.name)[name]
        except ValueError as e:
            self.logger.error(e)
            raise

    def get_general_settings(self) -> Dict[str, Union[str, List[str]]]:
        return self.get_settings('General')

    def get_addresses(self) -> Dict[str, Union[str, List[str]]]:
        return self.get_settings('Addresses')
>>>>>>> develop

    def decide_on_msg(self, msg: Message) -> None:
        # TODO : realise logic
        decision = self.decider.decide(msg)
        if decision.allowed:
            self.thinker.add_task_in(msg)
        else:
            pass  # should be send back or whereever

    def execute_com(self, msg: Message):
        msg_i: Message = None
        com: str = msg.data.info.com
        parameters: Dict[str, Any] = msg.data.info.parameters
        if com in self.available_public_functions():
            f = getattr(self, com)
            if parameters.keys() == signature(f).parameters.keys():
                result, comments = f(**parameters)
                if result:
                    msg_i = MsgGenerator.done_it(self, msg_i=msg, result=result, comments=comments)
            else:
                comments = f'Incorrect {parameters} were send. Should be {signature(f).parameters.keys()}'
        else:
            comments = f'com: {com} is not available for Service {self.id}. See {self.available_public_functions()}'
        if not msg_i:
            msg_i = MsgGenerator.error(self, msg_i=msg, comments=comments)
        self.thinker.msg_out(True, msg_i)

    @staticmethod
    def exec_mes_every_n_sec(f: Callable[[Any], bool], delay=5, n_max=10, specific={}) -> None:
<<<<<<< HEAD
        print("_exec_mes_every_n_se")
=======
>>>>>>> develop
        i = 0
        if delay > 5:
            delay = 5
        from time import sleep
        flag = True
        while flag and i <= n_max:
            i += 1
<<<<<<< HEAD
=======
            print(f'i = {i}')
>>>>>>> develop
            sleep(delay)
            if f:
                flag = f(**specific)

<<<<<<< HEAD
=======

>>>>>>> develop
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
        sleep(0.1)
        info_msg(self, 'STARTED')
        self.send_status_pyqt()

    def _stop_messaging(self):
        """Stop messaging part of Device"""
        info_msg(self, 'STOPPING')
        stop_msg = MsgGenerator.shutdown_info(device=self, reason='normal shutdown')
        self.messenger.send_msg(stop_msg)
        sleep(1)
        self.thinker.pause()
        self.messenger.pause()
        self.thinker.stop()
        sleep(0.5)
        self.messenger.stop()
        sleep(0.1)
        self.send_status_pyqt()
        self.device_status.messaging_paused = False
        self.device_status.messaging_on = False
        self.decider = None
        self.thinker = None
        self.messenger = None
        sleep(0.1)
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

    def info(self) -> Dict[str, Union[DeviceStatus, Any]]:
        from collections import OrderedDict as od
        info = od()
        info['device_status'] = self.device_status
        info['messenger_status'] = self.messenger.info()
        info['thinker_status'] = self.thinker.info()
        info['decider_status'] = self.decider.info()
        return info

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

    def update_config(self, message: str):
        # TODO: realize
        self.logger.info('Config is updated: ' + message)

    def __del__(self):
        self.logger.info(f"Instance of class {self.__class__.__name__}: {self.name} is deleted")
        del self


class Server(Device):

    def __init__(self, **kwargs):
        from communication.logic.thinkers import ServerCmdLogic
        from communication.messaging.messengers import ServerMessenger
        from devices.soft.deciders import ServerDecider
        cls_parts = {'Thinker': ServerCmdLogic,
                     'Decider': ServerDecider,
                     'Messenger': ServerMessenger}
        kwargs['cls_parts'] = cls_parts
        if 'DB_command' not in kwargs:
            kwargs['DB_command'] = "SELECT parameters from SERVER_settings where name = 'default'"
        self.services_available = []
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

    def available_public_functions(self) -> Dict[str, Dict[str, Any]]:
        # TODO: realize
        return {}

    def activate(self, flag: bool):
        """Server is always active"""
        self.logger.info("""Server is always active""")

    def description(self) -> Dict[str, Any]:
        # TODO: realize
        return {}

    def messenger_settings(self):
        # FIXME:...
        pass

    def start(self):
        super().start()

    def power(self, flag: bool):
        """Power of server is always ON"""
        self.logger.info("""Power of server is always ON, """)

    def send_status_pyqt(self, com=''):
        super().send_status_pyqt(com='status_server_info_full')


class Client(Device):
    """
    class Client communicates with Server to get access to Service it is bound to
    through realdevices determined within the model of PyQT application devoted to this task.
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
        self.server_msgn_id = ''
        # initialize_logger(app_folder / 'bin' / 'LOG', file_name=kwargs['name'])
        super().__init__(**kwargs)
        self.device_status = DeviceStatus(active=True, power=True)  # Power is always ON for client and it is active

    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        # TODO: add functionality
        pass

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

    def power(self, flag: bool):
        """Power of client is alway ON"""
        self.logger.info('Power is ON')

    def send_status_pyqt(self, com=''):
        super().send_status_pyqt(com='status_client_info')


class Service(Device):
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
        self.server_msgn_id = ''
        # initialize_logger(app_folder / 'bin' / 'LOG', file_name=kwargs['name'])
        super().__init__(**kwargs)

    @abstractmethod
    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        pass

    @abstractmethod
    def description(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def activate(self, flag: bool):
        """realization must be done in real hardware controllers"""
        pass

    def power(self, flag: bool):
        from communication.messaging.message_utils import MsgGenerator
        msg = MsgGenerator.power_on_demand(self, flag)
        self.send_msg_externally(msg)

    def messenger_settings(self):
        for adr in self.messenger.addresses['server_publisher']:
            try:
                self.messenger.subscribe_sub(address=adr)
            except Exception as e:
                a = e
                print(e)

    def send_status_pyqt(self, com=''):
        super().send_status_pyqt(com='status_service_info')


class DeviceFactory:

    @staticmethod
    def make_device(**kwargs):
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

                db_conn, cur = create_connectionDB(kwargs['db_path'])
                device_name = executeDBcomm(cur,
                                            f"SELECT device_name from DEVICES_settings where device_id='{device_id}'")

                if not device_name:
                    err = f'DeviceFactory Crash: {device_id} is not present in DB'
                    module_logger.error(err)
                    raise BaseException(err)
                device_name = device_name[0]

                project_type = executeDBcomm(cur,
                                             f"SELECT project_type from DEVICES_settings where device_id='{device_id}'")
                project_type = project_type[0]

                from importlib import import_module
                module_comm_thinkers = import_module('communication.logic.thinkers')
                if project_type == 'Client':
                    module_devices = import_module('devices.virtualdevices')
                elif project_type == 'Service':
                    module_devices = import_module('devices.realdevices')
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
