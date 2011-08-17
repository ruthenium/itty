from .base import (HTTP_MAPPINGS,
        Callback as _Callback,
        Error as _Error,
        Request,
        Response,
        static_file,
        EnvironmentError,
        Forbidden,
        NotFound,
        AppError,
        Redirect,
        App,
        run_app)

APP_METHODS = { }

class Callback(_Callback):

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return self._func

    @classmethod
    def decorator(cls, pattern):
        def wrapper(func):
            res = cls(pattern, func)
            APP_METHODS[func.func_name] = res
            return func
        return wrapper

class GetCallback(Callback):
    method = 'GET'

get = GetCallback.decorator

class PostCallback(Callback):
    method = 'POST'

post = PostCallback.decorator

class PutCallback(Callback):
    method = 'PUT'

put = PutCallback.decorator

class DeleteCallback(Callback):
    method = 'DELETE'

delete = DeleteCallback.decorator


class Error(_Error):

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return self._func

    @classmethod
    def decorator(cls, status):
        def wrapper(func):
            res = cls(func, status)
            APP_METHODS[func.func_name] = res
            return func
        return wrapper

error = Error.decorator

def run_itty(host='localhost', port=8080, adapter='wsgiref'):
    return run_app(type('IttyMainApplication',
                            (base.App, ),
                            APP_METHODS),
                        host, port, adapter)
