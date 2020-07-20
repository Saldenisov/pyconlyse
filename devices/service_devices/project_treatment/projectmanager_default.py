"""
11/07/2020 DENISOV Sergey
projectmanager_default.py contains abstract services capable of treating experiments datastructures:
open, analyze, transform
"""
from devices.service_devices.project_treatment.projectmanager_controller import ProjectManager_controller


class ProjectManager_default(ProjectManager_controller):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)