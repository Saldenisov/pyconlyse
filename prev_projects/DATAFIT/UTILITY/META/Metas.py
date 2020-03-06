"""
Модуль реализации метакласса, необходимого для работы представления.

pyqtWrapperType - метакласс общий для оконных компонентов Qt.
ABCMeta - метакласс для реализации абстрактных суперклассов.

MMeta - метакласс для представления.
"""

from PyQt5.QtCore import pyqtWrapperType
from abc import ABCMeta


class Meta(pyqtWrapperType, ABCMeta):
    pass
