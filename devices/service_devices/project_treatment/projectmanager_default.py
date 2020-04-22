"""
11/07/2020 DENISOV Sergey
projectmanager_default.py contains abstract services capable of treating experiments data:
open, analyze, transform
"""
import numpy as np
import os
from abc import abstractmethod
from datetime import datetime
from itertools import chain, tee
import hashlib
from pathlib import Path
from time import time_ns
from typing import Union, Dict, Any, Tuple, Iterable, Generator
from database import db_create_connection, db_close_conn, db_execute_select, db_execute_insert
from devices.devices import Service
from devices.service_devices.project_treatment.projectmanager_controller import ProjectManager_controller
from errors.myexceptions import DeviceError
from utilities.myfunc import paths_to_dict
from utilities.data.datastructures.mes_independent import (CmdStruct, FuncActivateInput, FuncActivateOutput,
                                                           FuncGetControllerStateInput, FuncGetControllerStateOutput)
from utilities.data.datastructures.mes_independent.measurments_dataclass import Measurement
from utilities.data.datastructures.mes_independent.projects_dataclass import *


class ProjectManager_default(ProjectManager_controller):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)