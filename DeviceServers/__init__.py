from DeviceServers.BASLER.DS_Basler_camera import DS_Basler_camera
from DeviceServers.BASLER.DS_BASLER_Widget import Basler_camera
from DeviceServers.NETIO.DS_Netio_pdu import DS_Netio_pdu
from DeviceServers.NETIO.DS_NETIO_Widget import Netio_pdu
from DeviceServers.OWIS.DS_OWIS_PS90 import DS_OWIS_PS90
from DeviceServers.OWIS.DS_OWIS_widget import OWIS_motor
from DeviceServers.STANDA.DS_Standa_Motor import DS_Standa_Motor
from DeviceServers.STANDA.DS_STANDA_Widget import Standa_motor
from DeviceServers.TopDirect.DS_TopDirect_Motor import DS_TopDirect_Motor
from DeviceServers.TopDirect.DS_TOPDIRECT_Widget import TopDirect_Motor


class_match = {DS_Basler_camera.__name__: Basler_camera,
               DS_Netio_pdu.__name__: Netio_pdu,
               DS_OWIS_PS90.__name__: OWIS_motor,
               DS_Standa_Motor.__name__: Standa_motor,
               DS_TopDirect_Motor.__name__: TopDirect_Motor}