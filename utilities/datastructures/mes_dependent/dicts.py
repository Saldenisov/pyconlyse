from collections import OrderedDict
from typing import Dict

from communication.messaging.messages import MessageExt, MsgComExt
from utilities.datastructures.mes_dependent.general import PendingDemand, PendingReply
from utilities.myfunc import info_msg, error_logger


class Events_Dict(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name_id = {}

    def __setitem__(self, key_id, event):
        if event.name not in self.name_id:
            super().__setitem__(key_id, event)
            self.name_id[event.name] = key_id
        else:
            raise KeyError(f'Name of event: {event.name} already exists in {self.name_id}')

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            if key in self.name_id:
                key = self.name_id[key]
                return super().__getitem__(key)
            else:
                raise KeyError('Neither event_id nor event_name were passed correctly to get the event...')

    def __delitem__(self, key):
        try:
            event_name = self[key].name
            super().__delitem__(key)
            del self.name_id[event_name]
        except KeyError:
            event_name = key
            if event_name in self.name_id:
                key = self.name_id[event_name]
                del self.name_id[event_name]
                super().__delitem__(key)

            else:
                raise KeyError('Neither event_id nor event_name were passed correctly to delete the event...')

    def __contains__(self, item):
        if super().__contains__(item):
            return True
        else:
            if item in self.name_id:
                return super().__contains__(self.name_id[item])


class MsgDict(OrderedDict):

    def __init__(self, name, dict_parent, size_limit, *args, **kwargs):
        self.__name__ = name
        self.name = name
        self.size_limit = size_limit
        self.dict_parent = dict_parent
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        if key not in self:
            self._check_size_limit()
            super().__setitem__(key, value)
        else:
            error = f'Key: {key} already exists in {self.name} {self}'
            if self.dict_parent:
                error_logger(self.dict_parent, self, error)
            raise KeyError(error)

    def _check_size_limit(self):
        if self.size_limit is not None:
            while len(self) > self.size_limit:
                element: MessageExt = self.popitem(last=False)[1]  # Remove first element
                if self.dict_parent:
                    info_msg(self.dict_parent, 'INFO', f'Limit size={self.size_limit} was exceeded for {self.name}, '
                                                       f'first element {element.short()} was removed')


class OrderedDictMesTypeCounter(OrderedDict):

    def __init__(self, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.mes_types: Dict[str, int] = {}

    def __setitem__(self, key, value):
        if key not in self:
            super().__setitem__(key, value)
            if isinstance(value, MessageExt):
                msg: MessageExt = value
            elif isinstance(value, PendingDemand) or isinstance(value, PendingReply):
                msg = value.message
            else:
                raise TypeError(f'Wrong type is passed {type(value)}')
            if msg.type in self.mes_types:
                self.mes_types[msg.type] += 1
            else:
                self.mes_types[msg.type] = 1
        else:
            raise KeyError(f'Key: {key} already exists in {self.name}')

    def __delitem__(self, key):
        try:
            value = self[key]
            super().__delitem__(key)
            if isinstance(value, MessageExt):
                msg: MessageExt = value
            elif isinstance(value, PendingDemand) or isinstance(value, PendingReply):
                msg = value.message

            mes_type = msg.body.type
            if self.mes_types[mes_type] == 1:
                del self.mes_types[mes_type]
            else:
                self.mes_types[mes_type] -= 1
        except (Exception, KeyError) as e:
            raise e