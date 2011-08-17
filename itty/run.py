def wsgiref_adapter(app, host, port):
    from wsgiref.simple_server import make_server
    srv = make_server(host, port, app)
    srv.serve_forever()


def appengine_adapter(app, host, port):
    from google.appengine.ext.webapp import util
    util.run_wsgi_app(app)


def cherrypy_adapter(app, host, port):
    # Experimental (Untested).
    from cherrypy import wsgiserver
    server = wsgiserver.CherryPyWSGIServer((host, port), app)
    server.start()


def flup_adapter(app, host, port):
    # Experimental (Untested).
    from flup.server.fcgi import WSGIServer
    WSGIServer(app, bindAddress=(host, port)).run()


def paste_adapter(app, host, port):
    # Experimental (Untested).
    from paste import httpserver
    httpserver.serve(app, host=host, port=str(port))


def twisted_adapter(app, host, port):
    from twisted.web import server, wsgi
    from twisted.python.threadpool import ThreadPool
    from twisted.internet import reactor
    
    thread_pool = ThreadPool()
    thread_pool.start()
    reactor.addSystemEventTrigger('after', 'shutdown', thread_pool.stop)
    
    ittyResource = wsgi.WSGIResource(reactor, thread_pool, app)
    site = server.Site(ittyResource)
    reactor.listenTCP(port, site)
    reactor.run()


def diesel_adapter(app, host, port):
    # Experimental (Mostly untested).
    from diesel.protocols.wsgi import WSGIApplication
    app = WSGIApplication(app, port=int(port))
    app.run()


def tornado_adapter(app, host, port):
    # Experimental (Mostly untested).
    from tornado.wsgi import WSGIContainer
    from tornado.httpserver import HTTPServer
    from tornado.ioloop import IOLoop
    
    container = WSGIContainer(app)
    http_server = HTTPServer(container)
    http_server.listen(port)
    IOLoop.instance().start()


def gunicorn_adapter(app, host, port):
    from gunicorn import version_info
    
    if version_info < (0, 9, 0):
        from gunicorn.arbiter import Arbiter
        from gunicorn.config import Config
        arbiter = Arbiter(Config({'bind': "%s:%d" % (host, int(port)), 'workers': 4}), app)
        arbiter.run()
    else:
        from gunicorn.app.base import Application
        
        class IttyApplication(Application):
            def init(self, parser, opts, args):
                return {
                    'bind': '{0}:{1}'.format(host, port),
                    'workers': 4
                }
            
            def load(self):
                return app
        
        IttyApplication().run()


def gevent_adapter(app, host, port):
    from gevent import wsgi
    wsgi.WSGIServer((host, int(port)), app).serve_forever()


def eventlet_adapter(app, host, port):
    from eventlet import wsgi, listen
    wsgi.server(listen((host, int(port))), app)


WSGI_ADAPTERS = {
    'wsgiref': wsgiref_adapter,
    'appengine': appengine_adapter,
    'cherrypy': cherrypy_adapter,
    'flup': flup_adapter,
    'paste': paste_adapter,
    'twisted': twisted_adapter,
    'diesel': diesel_adapter,
    'tornado': tornado_adapter,
    'gunicorn': gunicorn_adapter,
    'gevent': gevent_adapter,
    'eventlet': eventlet_adapter,
}

