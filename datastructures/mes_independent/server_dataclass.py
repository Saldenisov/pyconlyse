from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from communication.interfaces import MessengerInter, ThinkerInter
from communication.messaging.message_types import AccessLevel, Permission
from datastructures.mes_independent.general import Desription, CmdStruct, FuncInput, FuncOutput


@dataclass
class FuncAuthenticateUserInput(FuncInput):
    user_email: str
    user_password: str
    com: str = 'authenticate_user'


@dataclass
class FuncAuthenticateUserOutput(FuncOutput):
    access_level: AccessLevel
    permission: Permission
    com: str = 'authenticate_user'


@dataclass
class FuncRegiserNewUserInput(FuncInput):
    user_name: str
    user_surname: str
    user_email: str
    user_password: str
    com: str = 'register_new_user'


@dataclass
class FuncRegiserNewUserOutput(FuncOutput):
    com: str = 'register_new_user'