#!/usr/bin/env python
# coding: utf-8
# twistd -ny webredis.tac
# original tornado/redis web interface by alexandre fiori http://fiorix.wordpress.com

import redis
import cyclone.web
from twisted.internet import defer
from twisted.application import service, internet
import engine

class IndexHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self):
        key = self.get_argument("key")
        try:
            value = yield self.settings.oper.queue_get(key.encode("utf-8"))
        except Exception, e:
            self.write("exception get: %s\n" % str(e))
        else:
            self.write("get: %s\n" % repr(value))
        self.finish()

    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def post(self):
        key = self.get_argument("key")
        value = self.get_argument("value")
        try:
            result = yield self.settings.oper.queue_add(key.encode("utf-8"), value.encode("utf-8"))
        except Exception, e:
            self.write("set: %s\n" % str(e))
        else:
            self.write("set: %s\n" % result)
        self.finish()


class InfoHandler(cyclone.web.RequestHandler):
    def get(self):
        self.write("redis: %s\n" % repr(self.settings.db))
        #self.settings.db.disconnect()


class XmlrpcHandler(cyclone.web.XmlrpcRequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def xmlrpc_get(self, key):
        value = yield self.settings.db.get(key)
        defer.returnValue(value)

    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def xmlrpc_set(self, key, value):
        result = yield self.settings.db.set(key, value)
        defer.returnValue(result)


class WebRedis(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/",       IndexHandler),
            (r"/info",   InfoHandler),
            (r"/xmlrpc", XmlrpcHandler),
        ]
        db = redis.ConnectionPool(defer=False)
        settings = {
            "db": db,
            "static_path": "./static",
            "oper": engine.RedisOperations(db)
        }

        cyclone.web.Application.__init__(self, handlers, **settings)


application = service.Application("webredis")
srv = internet.TCPServer(8888, WebRedis())
srv.setServiceParent(application)
