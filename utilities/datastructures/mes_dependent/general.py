from dataclasses import dataclass
from time import time

from communication.messaging.messages import MessageExt


@dataclass(order=True)
class PendingDemand:
    message: MessageExt
    time: float = time()


@dataclass(order=True)
class PendingReply:
    message: MessageExt
    attempt: int = 0
    time: float = time()
