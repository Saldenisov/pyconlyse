"""
Created on 10 Jan 2017

@author: Sergey Denisov
"""
from functools import wraps
from typing import Any
from time import sleep
import inspect


def development_mode(dev: bool, with_return: Any):
    def decorator_function(func):
        @wraps(func)
        def inner(*args, **kwargs):
            if not dev:
                return func(*args, **kwargs)
            else:
                if with_return:
                    return with_return
        return inner
    return decorator_function


def dll_lock(func):
    @wraps(func)
    def inner(self, *args, **kwargs):
        i = 0
        # self.info(f'In {func}', True)
        # self.info(f'Caller: {inspect.stack()[1].function} : {inspect.stack()[2].function} : {inspect.stack()[3].function}', True)

        while self._dll_lock and i < 10:
            sleep(0.1)
            i += 1
            # self.info(f'Waiting for {func} : {i}', True)

        if self.dll:
            self._dll_lock = True
            res = func(self, *args, **kwargs)
            self._dll_lock = False
        else:
            res = False
        return res
    return inner

def dll_lock_for_class(func):
    @wraps(func)
    def inner(self, *args, **kwargs):
        self._dll_lock = True
        res = func(self, *args, **kwargs)
        self._dll_lock = False
        sleep(0.001)
        return res
    return inner


def make_loop(func):
    from threading import Thread
    from time import sleep

    @wraps(func)
    def func_wrapper(*args, **kwargs):
        try:
            obj = kwargs['obj']
        except KeyError:
            obj = args[0]
        if not hasattr(obj, 'active') or not hasattr(obj, 'paused'):
            raise Exception(f'{obj} does not have attribute: active or paused')

        def f(*internal_args, **internal_kwargs):
            while obj.active:
                if not obj.paused:
                    sleep(internal_kwargs['await_time'])
                    func(*internal_args, **internal_kwargs)
                else:
                    sleep(internal_kwargs['await_time'] * 10)
            obj.logger.info('Loop thread is off')

        obj.send_loop_thread = Thread(target=f, args=args, kwargs=kwargs)
        obj.send_loop_thread.start()

    return func_wrapper


def once(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if inner.called:
            print(func.__name__ + ' already done')
            return None
        if not inner.called:
            inner.called = True
            return func(*args, **kwargs)
    inner.called = False
    return inner


def save_parameters(commands: {}, messenger, logger, path):
    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            kwargs['commands'] = commands
            kwargs['messenger'] = messenger
            kwargs['logger'] = logger
            kwargs['path'] = path
            return func(*args, **kwargs)
        return inner
    return decorator


def turn_off(active=True):

    def inner_decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            if active:
                pass
            else:
                return f(*args, **kwargs)
        return inner

    return inner_decorator
