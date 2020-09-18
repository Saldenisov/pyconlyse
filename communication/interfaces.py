from abc import ABC
from threading import Thread


class ThinkerInter(ABC):
    pass


class MessengerInter(ABC, Thread):
    pass


class Message(ABC):
    """
    Interface Class for MessageExt and MessageInt
    """
    pass
