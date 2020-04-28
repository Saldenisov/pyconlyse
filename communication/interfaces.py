from abc import ABC
from threading import Thread


class ThinkerInter(ABC):
    pass


class MessengerInter(ABC, Thread):
    pass


class MessageInter(ABC):
    """
    Interface Class for Message
    """
    pass


