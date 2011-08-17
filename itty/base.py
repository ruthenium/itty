import os

from sys import exc_info
from traceback import format_exception

import re

from StringIO import StringIO
from collections import defaultdict

from inspect import getmembers
from types import MethodType

from mimetypes import guess_type
from cgi import FieldStorage

try:
    from urlparse import parse_qs
except ImportError:
    from cgi import parse_qs

HTTP_MAPPINGS = {
    100: 'CONTINUE',
    101: 'SWITCHING PROTOCOLS',
    200: 'OK',
    201: 'CREATED',
    202: 'ACCEPTED',
    203: 'NON-AUTHORITATIVE INFORMATION',
    204: 'NO CONTENT',
    205: 'RESET CONTENT',
    206: 'PARTIAL CONTENT',
    300: 'MULTIPLE CHOICES',
    301: 'MOVED PERMANENTLY',
    302: 'FOUND',
    303: 'SEE OTHER',
    304: 'NOT MODIFIED',
    305: 'USE PROXY',
    306: 'RESERVED',
    307: 'TEMPORARY REDIRECT',
    400: 'BAD REQUEST',
    401: 'UNAUTHORIZED',
    402: 'PAYMENT REQUIRED',
    403: 'FORBIDDEN',
    404: 'NOT FOUND',
    405: 'METHOD NOT ALLOWED',
    406: 'NOT ACCEPTABLE',
    407: 'PROXY AUTHENTICATION REQUIRED',
    408: 'REQUEST TIMEOUT',
    409: 'CONFLICT',
    410: 'GONE',
    411: 'LENGTH REQUIRED',
    412: 'PRECONDITION FAILED',
    413: 'REQUEST ENTITY TOO LARGE',
    414: 'REQUEST-URI TOO LONG',
    415: 'UNSUPPORTED MEDIA TYPE',
    416: 'REQUESTED RANGE NOT SATISFIABLE',
    417: 'EXPECTATION FAILED',
    500: 'INTERNAL SERVER ERROR',
    501: 'NOT IMPLEMENTED',
    502: 'BAD GATEWAY',
    503: 'SERVICE UNAVAILABLE',
    504: 'GATEWAY TIMEOUT',
    505: 'HTTP VERSION NOT SUPPORTED',
}

class EnvironmentError(Exception):
    """Thrown, when app is configured improperly."""

    pass


class RequestError(Exception):
    """A base exception for HTTP errors to inherit from."""
    status = 404
    
    def __init__(self, message, hide_traceback=False):
        super(RequestError, self).__init__(message)
        self.hide_traceback = hide_traceback


class Forbidden(RequestError):
    status = 403


class NotFound(RequestError):
    status = 404
    
    def __init__(self, message, hide_traceback=True):
        super(NotFound, self).__init__(message)
        self.hide_traceback = hide_traceback


class AppError(RequestError):
    status = 500


class Redirect(RequestError):
    """
    Redirects the user to a different URL.
    
    Slightly different than the other HTTP errors, the Redirect is less
    'OMG Error Occurred' and more 'let's do something exceptional'. When you
    redirect, you break out of normal processing anyhow, so it's a very similar
    case."""
    status = 302
    url = ''
    hide_traceback = True
    
    def __init__(self, url):
        self.url = url
        self.args = ["Redirecting to '%s'..." % self.url]


class lazyproperty(object):
    """A property whose value is computed only once. """
    def __init__(self, function):
        self._function = function

    def __get__(self, obj, _=None):
        if obj is None:
            return self
        
        value = self._function(obj)
        setattr(obj, self._function.func_name, value)
        return value


class Request(object):
    """An object to wrap the environ bits in a friendlier way."""
    GET = {}

    def __init__(self, environ, start_response):
        self._environ = environ
        self._start_response = start_response

        self.path = _add_slash(self._environ.get('PATH_INFO', ''))
        self.script_name = self._environ.get('SCRIPT_NAME', '')
        self.user = self._environ.get('REMOTE_USER', None)
        self.method = self._environ.get('REQUEST_METHOD', 'GET').upper()
        self.query = self._environ.get('QUERY_STRING', '')
        try:
            self.content_length = int(self._environ.get('CONTENT_LENGTH',
                0))
        except ValueError:
            self.content_length = 0

        self.GET = self.build_get_dict()

    @lazyproperty
    def POST(self):
        return self.build_complex_dict()

    @lazyproperty
    def PUT(self):
        return self.build_complex_dict()

    @lazyproperty
    def body(self):
        """Content of the request."""
        return self._environ['wsgi.input'].read(self.content_length)

    def build_get_dict(self):
        """Takes GET data and rips it apart into a dict."""
        raw_query_dict = parse_qs(self.query, keep_blank_values=1)
        query_dict = {}

        for key, value in raw_query_dict.items():
            if len(value) <= 1:
                query_dict[key] = value[0]
            else:
                # Since it's a list of multiple items, we must have seen more than
                # one item of the same name come in. Store all of them.
                query_dict[key] = value

        return query_dict


    def build_complex_dict(self):
        """Takes POST/PUT data and rips it apart into a dict."""
        raw_data = FieldStorage(fp=StringIO(self.body), environ=self._environ)
        query_dict = {}

        for field in raw_data:
            if isinstance(raw_data[field], list):
                # Since it's a list of multiple items, we must have seen more than
                # one item of the same name come in. Store all of them.
                query_dict[field] = [fs.value for fs in raw_data[field]]
            elif raw_data[field].filename:
                # We've got a file.
                query_dict[field] = raw_data[field]
            else:
                query_dict[field] = raw_data[field].value

        return query_dict

    def write_error(self, message):
        self._environ['wsgi.errors'].write(message)


def _to_ascii(els):
    '''Converts to ascii only two-tuple'''
    def _ascii(data):
        if not isinstance(data, unicode):
            return str(data)
        try:
            return data.encode('us-ascii')
        except UnicodeError:
            raise EnvironmentError
    return (_ascii(els[0]), _ascii(els[1]))


class Response(object):
    headers = []
    
    def __init__(self, output, headers=[], status=200, content_type='text/html'):
        self.output = output
        self.content_type = content_type
        self.status = status
        if not isinstance(headers, list):
            headers = list(headers)
        self.headers = headers
    
    def add_header(self, key, value):
        self.headers.append((key, value))

    def send(self, start_response):
        status = '%d %s' % (self.status, HTTP_MAPPINGS.get(self.status))
        headers = [('Content-Type',
            '%s; charset=utf-8' % self.content_type)] + self.headers

        start_response(status, map(_to_ascii, headers))

        if isinstance(self.output, unicode):
            return self.output.encode('utf-8')
        return self.output

def _add_slash(url):
    """Adds a trailing slash for consistency in urls."""
    return url if url.endswith('/') else url + '/'

def static_file(name, root, content_type=None):
    if name is None:
        raise NotFound('No filename') # serve dirs?

    filename = (name.rstrip('/')
            .replace('//', '/')
            .replace('/./', '/')
            .replace('/../', '/'))

    path = os.path.join(root, filename)

    if not os.path.exists(path):
        raise NotFound('No such file')

    if not os.access(path, os.R_OK):
        raise Forbidden('You do not have a permission to access this'
                ' file.')

    if not content_type:
        content_type, enc = guess_type(name)
        if not content_type:
            content_type = 'text/plain'

    if (content_type.startswith('text') or content_type.endswith('xml')
            or content_type.endswith('json')):
        mode = 'r'
    else:
        mode = 'rb'
    return Response(open(path, mode).read(), content_type=content_type)

#########################################################################

class Callback(object):

    def __init__(self, pattern, func):
        self.url = pattern
        self.regex = re.compile(r'^%s$' % _add_slash(pattern))
        self._func = func

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return MethodType(self._func, instance, owner)

    @classmethod
    def decorator(cls, pattern):
        def wrapper(func):
            return cls(pattern, func)
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

class Error(object):
    def __init__(self, func, status):
        self.status = status
        self._func = func

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return MethodType(self._func, instance, owner)

    @classmethod
    def decorator(cls, status):
        def wrapper(func):
            return cls(func, status)
        return wrapper

error = Error.decorator

#######################################################

class AppMeta(type):

    def __init__(cls, *args, **kwargs):
        super(AppMeta, cls).__init__(*args, **kwargs)
        cls.setup()

    def setup(cls):
        cls.callbacks = defaultdict(list)
        cls.error_handlers = {}
        for n, o in getmembers(cls):
            if isinstance(o, Error):
                cls.error_handlers[o.status] = n
            elif isinstance(o, Callback):
                cls.callbacks[o.method].append((o.regex, o.url, n))


class App(object):
    __metaclass__ = AppMeta

    def __call__(self, environ, start_response):

        try:
            request = Request(environ, start_response)
        except Exception, e:
            raise EnvironmentError(e.message)

        try:
            (re_url, url, name), kwargs = self.find_callback(request)
            response = getattr(self, name)(request, **kwargs)
        except Exception, e:
            response = self.handle_error(request, e) # we can not throw
            # an exception from here.

        if not isinstance(response, Response):
            response = Response(response)

        return response.send(start_response)

    def handle_error(self, request, exception):
        if not getattr(exception, 'hide_traceback', False):
            request.write_error('%s occurred on "%s":'
                    ' %s\nTraceback: %s' % (exception.__class__,
                        request.path,
                        exception,
                        ''.join(format_exception(*exc_info())))
                    )

        if isinstance(exception, RequestError):
            status = getattr(exception, 'status', 404)
        else:
            status = 500

        if status in self.error_handlers:
            return getattr(self,
                    self.error_handlers[status])(request, exception)
        return Response(HTTP_MAPPINGS[status].capitalize(),
                status=status, content_type='text/plain')

    def find_callback(self, request):
        if not request.method in self.callbacks:
            raise NotFound('Http method %s is not supported' % request.method)

        for url_set in self.callbacks[request.method]:
            match = url_set[0].search(request.path)

            if match is not None:
                return (url_set, match.groupdict())

        raise NotFound('Nothing here')

    @error(302)
    def redirect(self, request, exception):
        return Response('', status=302, content_type='text/plain',
                headers=[('Location', exception.url)])

def run_app(app_cls, host='localhost', port=8080, adapter='wsgiref'):
    from .run import WSGI_ADAPTERS
    if not adapter in WSGI_ADAPTERS:
        raise RuntimeError("Adapter '%s' is not supported. Please "
                "choose a different adapter." % adapter)

    try:
        WSGI_ADAPTERS[adapter](app_cls(), host, port)
    except KeyboardInterrupt:
        print 'Shutting down. Have a nice day'
