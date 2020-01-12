
"""
Created on 7 juin 2016

@author: saldenisov

"""

import socket
from contextlib import closing
from typing import Tuple, List
import logging
from datetime import datetime
from hashlib import md5
from random import randint
from time import sleep
from typing import Any

import numpy as np

from errors.myexceptions import WrongInfoType

module_logger = logging.getLogger(__name__)


def error_logger(obj: object, func, e):
    obj.logger.error(f'func:{func.__name__} {e}')


def dict_to_str_repr(d: dict) -> str:
    return "\n".join("{}: {}".format(k, v) for k, v in d.items())


def list_to_str_repr(l: list) -> str:
    if l:
        return "\n".join("{}".format(k) for k in l)
    else:
        return ""


def info_msg(obj: object, msg_type: str, extra=''):
    msg = ['INITIALIZING', 'INITIALIZED', 'NOT INITIALIZED', 'STARTING', 'STARTED', 'STOPPING', 'STOPPED',
           'CREATING', 'CREATED', 'NOT CREATED', 'REQUEST', 'DEMAND', 'REPLY', 'REPLY_IN', 'INFO', 'FORWARD',
           'DENIED', 'STRANGE', 'PAUSING',
           'PAUSED', 'UNPAUSING','UNPAUSED']

    if msg_type in msg:
        if msg_type == 'INITIALIZING':
            r = f'{obj.name}{extra} is initializing'
        elif msg_type == 'INITIALIZED':
            r = f'{obj.name}{extra} is initialized'
        elif msg_type == 'NOT INITIALIZED':
            r = f'{obj.name}{extra} is not initialized'
        elif msg_type == 'STARTING':
            r = f'{obj.name}{extra} is starting'
        elif msg_type == 'STARTED':
            r = f'{obj.name}{extra} is started'
        elif msg_type == 'STOPPING':
            r = f'{obj.name}{extra} is stopping'
        elif msg_type == 'STOPPED':
            r = f'{obj.name}{extra} is stopped'
        elif msg_type == 'PAUSING':
            r = f'{obj.name}{extra} is pausing'
        elif msg_type == 'PAUSED':
            r = f'{obj.name}{extra} is paused'
        elif msg_type == 'UNPAUSING':
            r = f'{obj.name}{extra} is unpausing'
        elif msg_type == 'UNPAUSED':
            r = f'{obj.name}{extra} is unpaused'
        elif msg_type == 'CREATING':
            r = f'{obj.name}{extra} is creating'
        elif msg_type == 'CREATED':
            r = f'{obj.name}{extra} is created'
        elif msg_type == 'NOT CREATED':
            r = f'{obj.name}{extra} is not created'
        elif msg_type == 'STRANGE':
            r = f'Something strange happened {obj.name}{extra}'
        elif msg_type == 'DENIED':
            r = 'Permission is denied'
        elif msg_type in ['REQUEST', 'DEMAND']:
            r = f'{msg_type}: {extra} \n____________________________\n'
        elif msg_type == 'INFO':
            r = f': {extra} \n____________________________\n'
        elif msg_type == 'FORWARD':
            r = f'FORWARD: {extra} \n++++++++++++++++++++++++++++ N: {obj._counter}\n'
        elif msg_type in ['REPLY', 'REPLY_IN']:
            r = f'{msg_type}: {extra} \n++++++++++++++++++++++++++++ N: {obj._counter}\n'

        obj.logger.info(r)
    else:
        raise WrongInfoType(f'func: {info_msg.__name__}: wrong type: {msg_type}')


def unique_id(name: [Any] = '') -> str:
    """
    Calculate md5 hash of date + system time + name
    :return: return tests_hardware uniqie id
    """
    if not name:
        name = ''
    else:
        if not isinstance(name, str):
            name = repr(name)

    date_time1 = str(datetime.now())
    sleep(10**-6)
    date_time2 = str(datetime.now())
    rint = randint(0, 1000)
    result = f'{date_time1}_{date_time2}_{rint}_{name}'
    return md5(result.encode('ascii')).hexdigest()


def get_local_ip() -> str:
    import ifaddr

    adapters = ifaddr.get_adapters()

    ips_l = []
    for adapter in adapters:
        for ip in adapter.ips:
            if ip.network_prefix < 64:
                ips_l.append(ip.ip)

    def get(ips_l):
        ip = None
        for ip in ips_l:
            if '129.' in ip:
                return ip
            elif '127' in ip:
                return ip
    # was before return str(gethostbyname(gethostname()))
    return get(ips_l)

def test_local_port(port):
    # https://docs.python.org/2/library/socket.html#example
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', port))  # Try to open port
        s.close()
        return False
    except OSError:
        return True


def get_free_port(scope: Tuple[int, str] = (5000, 6000), exclude: List[int] = []):
    if not scope:
        i = 0
        while True:
            i += 1
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.bind(('', 0))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if s.getsockname()[1] not in exclude:
                    return s.getsockname()[1]
            if i > 1000:
                raise Exception('get_free_port search exceeded 1000')

    else:
        sc = []
        for el in scope:
            sc.append(int(el))
        scope = tuple(sc)

        for port in range(scope[0], scope[1]):
            if port not in exclude:
                if not test_local_port(port):
                    return port
        raise Exception(f'Free port cannot be found in the range {scope}')


def verify_port(port: str, exclude=[]):
    if ':' in port:
        ports = tuple(port.split(':'))
        return get_free_port(scope=ports,exclude=exclude)
    else:
        port = int(port)
        if test_local_port(port) or port in exclude:
            return get_free_port(scope=(port, port+1000), exclude=exclude)
        return port


def ndarray_tostring(arr):
    '''
    Convert ndarray to tab separated string

    >>> import numpy as np
    >>> tests_hardware = np.array([1, 2, 3])
    >>> b = ndarray_tostring(tests_hardware)
    >>> print(b)
    1.000
    2.000
    3.000
    >>> c = np.array([[1, 2, 3],[1, 2, 3]])
    >>> d = ndarray_tostring(c)
    >>> print(repr(d))
    '1.000\\t2.000\\t3.000\\n1.000\\t2.000\\t3.000'
    >>> e = np.array([[1, 2, None],[1, None, 3]])
    >>> f = ndarray_tostring(e)
    >>> print(repr(f))
    '1.000\\t2.000\\t--\\n1.000\\t--\\t3.000'
    '''
    s = ''
    size = len(np.shape(arr))

    if size == 1:
        for i in arr:
            if i == None or np.isnan(i):
                s += '--'
            else:
                s += format(i, '.3f')
            s += '\n'
        s = s[:-1]

    if size == 2:
        for i in arr:
            for j in i:
                if j == None or np.isnan(j):
                    s += '--'
                else:
                    s += format(j, '.3f')
                s += '\t'
            s = s[:-1]
            s += '\n'
        s = s[:-1]

    if size > 2:
        s = 'wrong numpy.ndarray size in ndarray_tostring'

    return s


def tuple_tostring(tuple_arr):
    """
    Takes tuple of arrays and convert them to string
    """
    pass


def dict_of_dict_to_array(dic):
    arr = []
    for key in dic:
        if not isinstance(dic[key], dict):
            arr.append(dic[key])
        else:
            arr.extend(dict_of_dict_to_array(dic[key]))
    return arr


if __name__ == "__main__":
    import doctest
    doctest.testmod()
