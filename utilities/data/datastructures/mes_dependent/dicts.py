from typing import Dict
from utilities.data.datastructures.mes_dependent.general import Connection, PendingDemand, PendingReply
from utilities.data.messages import Message
from collections import OrderedDict

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
        finally:
            print(f'event {event_name} is deleted')

    def __contains__(self, item):
        if super().__contains__(item):
            return True
        else:
            if item in self.name_id:
                return super().__contains__(self.name_id[item])


class Connections_Dict(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messenger_id = {}

    def __setitem__(self, key_id, connection: Connection):
        msgn_id = connection.device_info.messenger_id
        if msgn_id not in self.messenger_id:
            super().__setitem__(key_id, connection)
            self.messenger_id[msgn_id] = key_id
        else:
            raise KeyError(f'Messenger id: {msgn_id} already exists in {self.messenger_id}')

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            if key in self.messenger_id:
                return super().__getitem__(self.messenger_id[key])
            else:
                raise KeyError('Neither device_id nor messenger_id were passed correctly to get the connection...')

    def __delitem__(self, key):
        try:
            connection: Connection = self[key]
            messenger_id = connection.device_info.messenger_id
            super().__delitem__(key)
            del self.messenger_id[messenger_id]
        except KeyError:
            messenger_id = key
            if messenger_id in self.messenger_id:
                key = self.messenger_id[messenger_id]
                del self.messenger_id[messenger_id]
                super().__delitem__(key)
            else:
                raise KeyError('Neither device_id nor messenger_id were passed correctly to delete the connection...')

    def __contains__(self, item):
        if super().__contains__(item):
            return True
        else:
            if item in self.messenger_id:
                return super().__contains__(self.messenger_id[item])


class OrderedDictMod(OrderedDict):

    def __init__(self, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name

    def __setitem__(self, key, value):
        if key not in self:
            super().__setitem__(key, value)
        else:
            raise KeyError(f'Key: {key} already exists in {self.name}    {self}')


class OrderedDictMesTypeCounter(OrderedDict):

    def __init__(self, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.mes_types: Dict[str, int] = {}

    def __setitem__(self, key, value):
        if key not in self:
            super().__setitem__(key, value)
            if isinstance(value, Message):
                msg: Message = value
            elif isinstance(value, PendingDemand) or isinstance(value, PendingReply):
                msg = value.message
            else:
                raise TypeError(f'Wrong type is passed {type(value)}')
            if msg.body.type in self.mes_types:
                self.mes_types[msg.body.type] += 1
            else:
                self.mes_types[msg.body.type] = 1
        else:
            raise KeyError(f'Key: {key} already exists in {self.name}')

    def __delitem__(self, key):
        try:
            value = self[key]
            super().__delitem__(key)
            if isinstance(value, Message):
                msg: Message = value
            elif isinstance(value, PendingDemand) or isinstance(value, PendingReply):
                msg = value.message

            mes_type = msg.body.type
            if self.mes_types[mes_type] == 1:
                del self.mes_types[mes_type]
            else:
                self.mes_types[mes_type] -= 1
        except (Exception, KeyError) as e:
            raise e