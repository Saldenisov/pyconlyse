'''
Created on 10 Jan 2017

@author: Sergey Denisov
'''
from typing import Union, Any
from functools import wraps

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


def development_mode(dev: bool, with_return: Any):
    def decorator_function(func):
        @wraps(func)
        def inner(*args, **kwargs):
            if not dev:
                return func(*args, **kwargs)
            else:
                if with_return != None:
                    return with_return
        return inner
    return decorator_function






