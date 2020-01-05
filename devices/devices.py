from pathlib import Path
import sys
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(Path(__file__).resolve().parents[1]))

import inspect
import logging
import sqlite3 as sq3
from abc import abstractmethod
from pathlib import Path
from time import sleep
from typing import Dict, Union

from PyQt5.QtCore import QObject, pyqtSignal

from DB.tools import create_connectionDB, executeDBcomm, close_connDB
from communication.interfaces import ThinkerInter, MessengerInter
from communication.messaging.message_utils import MsgGenerator
from errors.messaging_errors import MessengerError
from errors.myexceptions import DeviceError
from devices.interfaces import DeciderInter, ExecutorInter, DeviceInter
from utilities.configurations import configurationSD
from utilities.data.datastructures.mes_independent import DeviceStatus, DeviceParts
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
                 parent: QObject=None,
                 DB_command: str='',
                 logger_new=True,
                 **kwargs):
        super().__init__()
        self._kwargs = kwargs
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
        self.long_name = f'{self.__class__.__name__}:{name}:{Device.n_instance}'
        self.parent: QObject = parent


        self.db_path = db_path
        self.config = configurationSD(self)

        self.connections: Dict[str, Connection] = Connections_Dict()

        self.cls_parts = cls_parts
        self.cls_parts_instances: DeviceParts

        self.device_status = DeviceStatus(*[False]*3)

        try:
            assert len(self.cls_parts) == 3
            for key, item in self.cls_parts.items():
                assert key in ['Messenger', 'Thinker', 'Decider']
                assert inspect.isclass(item)
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
            self.db_conn = close_connDB(self.db_conn)
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
    def description(self):
        pass

    def start(self):
        info_msg(self, 'STARTING')
        self.thinker.start()
        self.messenger_settings()
        self.messenger.start()
        sleep(0.1)
        info_msg(self, 'STARTED')
        self.device_status.on = True
        self.device_status.active = True
        self.send_status_pyqt()

    def stop(self):
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
        self.device_status = DeviceStatus(*[False] * 3)
        self.send_status_pyqt()
        self.decider = None
        self.thinker = None
        self.messenger = None
        sleep(0.1)
        info_msg(self, 'STOPPED')

    @abstractmethod
    def messenger_settings(self):
        pass

    @abstractmethod
    def activate(self):
        pass

    @abstractmethod
    def deactivate(self):
        pass

    def info(self):
        from collections import OrderedDict as od
        info = od()
        info['device_status'] = self.device_status
        info['messenger_status'] = self.messenger.info()
        info['thinker_status'] = self.thinker.info()
        info['decider_status'] = self.decider.info()
        return info

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

    def pause(self):
        self.thinker.pause()
        self.messenger.pause()
        self.device_status.paused = True
        self.send_status_pyqt()

    def unpause(self):
        self.messenger.unpause()
        self.thinker.unpause()
        self.device_status.paused = False
        self.send_status_pyqt()

    def send_msg_externally(self, msg: Message):
        self.messenger.add_msg_out(msg)

    def decide_on_msg(self, msg: Message):
        # TODO : realise logic
        decision = self.decider.decide(msg)
        if decision.allowed:
            self.thinker.add_task_in(msg)
        else:
            pass # should be send back or whereever

    def update_config(self, message: str):
        """
        """
        self.logger.info('Config is updated: ' + message)

    def get_addresses(self) -> dict:
        res = self.config.config_to_dict(self.name)['Addresses']
        return res

    def get_general_settings(self) -> dict:
        return self.config.config_to_dict(self.name)['General']

    def available_public_functions(self):
        pass

    def __del__(self):
        self.logger.info(f"Instance of class {self.__class__.__name__}: {self.long_name} is deleted")
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
        #initialize_logger(app_folder / 'bin' / 'LOG', file_name="Server")

        super().__init__(**kwargs)

    def description(self):
        return 'Main Server'

    @property
    def services_running(self):
        services_running = {}
        for device_id, connection in self.connections.items():
            info = connection.device_info
            if info.type == 'service':
                services_running[device_id] = info.name
        return services_running

    @property
    def clients_running(self):
        clients_running = {}
        for device_id, connection in self.connections.items():
            info = connection.device_info
            if info.type == 'client':
                clients_running[device_id] = info.name
        return clients_running


    def stop(self):
       super().stop()

    def messenger_settings(self):
        pass

    def activate(self):
        pass

    def deactivate(self):
        pass

    def _find_available_services(self):
        self.services_available = ['DLemulate', 'DL2axis']

    def send_status_pyqt(self, com=''):
        super().send_status_pyqt(com='status_server_info_full')


class Service(Device):

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
        #initialize_logger(app_folder / 'bin' / 'LOG', file_name=kwargs['name'])
        super().__init__(**kwargs)

    def activate(self):
        pass

    def deactivate(self):
        pass

    def messenger_settings(self):
        self.messenger.subscribe_sub(address=self.messenger.addresses['server_publisher'])

    def send_status_pyqt(self, com=''):
        super().send_status_pyqt(com='status_service_info')


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
        #initialize_logger(app_folder / 'bin' / 'LOG', file_name=kwargs['name'])
        super().__init__(**kwargs)

    def messenger_settings(self):
        if isinstance(self.messenger.addresses['server_publisher'], list):
            for adr in self.messenger.addresses['server_publisher']:
                self.messenger.subscribe_sub(address=adr)
        else:
            self.messenger.subscribe_sub(address=self.messenger.addresses['server_publisher'])

    def activate(self):
        pass

    def deactivate(self):
        pass

    def send_status_pyqt(self, com=''):
        super().send_status_pyqt(com='status_client_info')


class DeviceFactory:

    @staticmethod
    def make_device(**kwargs):
        if 'cls' in kwargs:
            cls = kwargs['cls']
            if issubclass(cls, Device):
                return cls(**kwargs)
            elif type(cls).__name__ == 'str':
                raise BaseException('DeviceFactory Crash')
            else:
                raise BaseException('DeviceFactory Crash')
        else:
            if 'device_id' in kwargs and 'db_path' in kwargs:
                device_id = kwargs['device_id']

                DB_cmd = f"SELECT device_name from DEVICES_settings where device_id = '{device_id}'"
                db_conn, cur = create_connectionDB(kwargs['db_path'])
                device_name = executeDBcomm(cur, DB_cmd)
                device_name = device_name[0]
                if not device_name:
                    raise BaseException(f'DeviceFactory Crash: {device_id} is not present in DB')

                DB_cmd = f"SELECT project_type from DEVICES_settings where device_id = '{device_id}'"
                db_conn, cur = create_connectionDB(kwargs['db_path'])
                project_type = executeDBcomm(cur, DB_cmd)
                project_type = project_type[0]

                from importlib import import_module
                module_comm_thinkers = import_module('communication.logic.thinkers')
                a = 'Client'
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
                raise BaseException('DeviceFactory Crash: cls or device_id or db_path were not passed')



