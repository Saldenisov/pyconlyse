"""
11/07/2020 DENISOV Sergey
projectmanager_default.py contains abstract services capable of treating experiments datastructures:
open, analyze, transform
"""
import numpy as np
from datetime import datetime
import hashlib
from pathlib import Path
from devices.devices import Service
from devices.service_devices.project_treatment.projectmanager_controller import ProjectManager_controller
from utilities.myfunc import paths_to_dict
from datastructures.mes_independent.projects_dataclass import *


class ProjectManager_default(ProjectManager_controller):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)