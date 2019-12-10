import logging
from abc import abstractmethod
from dataclasses import dataclass

from devices.interfaces import DeciderInter
from utilities.data.messages import Message
from utilities.myfunc import unique_id


@dataclass()
class Decision:
    allowed: bool = False
    where_to_send: str = ''
    comment: str = ''


class Decider(DeciderInter):
    # TODO: it is needed to be checked how this class is being used troughout the project
    n_instance = 0

    def __init__(self, parent):
        Decider.n_instance += 1
        self.logger = logging.getLogger(f'{__name__}.{self.__class__.__name__}')
        self.name = f'{self.__class__.__name__}:{parent.name}:{Decider.n_instance}'
        self.id = f'{self.name}:{unique_id(self.name)}'

    @abstractmethod
    def check_permissions(self, msg: Message) -> dict:
        pass

    @abstractmethod
    def decide(self, msg: Message) -> Decision:
        pass

    def info(self):
        from collections import OrderedDict as od
        info = od()
        info['id'] = self.id
        return info


class ServerDecider(Decider):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def decide(self, msg: Message):
        if self.check_permissions(msg):
            return Decision(True, 'Thinker')
        else:
            return Decision(False, 'Back', 'Reason of refusal')

    def check_permissions(self, msg: Message) -> bool:
        return True


class ServiceDecider(Decider):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def check_permissions(self, msg: Message) -> dict:
        return True

    def decide(self, msg: Message):
        if self.check_permissions(msg):
            return Decision(True, 'Thinker')
        else:
            return Decision(False, 'Back', 'Reason of refusal')



class ClientDecider(Decider):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def check_permissions(self, msg: Message) -> dict:
        return True

    def decide(self, msg: Message):
        if self.check_permissions(msg):
            return Decision(True, 'Thinker')
        else:
            return Decision(False, 'Back', 'Reason of refusal')
