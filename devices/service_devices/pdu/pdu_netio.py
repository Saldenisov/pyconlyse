""""
saldenisov
created: 12/08/2020
"""
from devices.service_devices.pdu.pdu_controller import PDUController, PDUError
from utilities.datastructures.mes_independent.pdu_dataclass import *
from utilities.myfunc import error_logger, info_msg

class PDUCtrl_NETIO(PDUController):

    def __init__(self, **kwargs):
        kwargs['pdu_class'] = PDUCtrl_NETIO
        super().__init__(**kwargs)
        self.tl_factory = None
        self.pylon_cameras = None

     

