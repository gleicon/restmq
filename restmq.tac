#!/usr/bin/env python
# coding: utf-8
# twistd -ny restmq.tac
# twisted/cyclone app skeleton copycat from fiorix's webredis.tac (http://fiorix.wordpress.com)
# gleicon moraes (http://zenmachine.wordpress.com | http://github.com/gleicon)

import txredis
import cyclone.web
import cyclone.escape
from twisted.internet import defer
from twisted.application import service, internet
import engine
from cmd_dispatch import CommandDispatch
from twisted.internet import task

class IndexHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self):
        queue = self.get_argument("queue")
        try:
            value = yield self.settings.oper.queue_get(queue.encode("utf-8"))
        except Exception, e:
            self.write("exception get: %s\n" % str(e))
        else:
            self.write("get: %s\n" % repr(value))
        self.finish()

    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def post(self):
        queue = self.get_argument("queue")
        value = self.get_argument("value")
        try:
            result = yield self.settings.oper.queue_add(queue.encode("utf-8"), value.encode("utf-8"))
        except Exception, e:
            self.write("set failed: %s\n" % str(e))
        else:
            self.write("set: %s\n" % result)
        self.finish()


class StatusHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self):
        # application/json or text/json ? 
        self.set_header("Content-Type", "text/plain")
        allqueues = yield self.settings.oper.queue_all()

        stats={'redis': repr(self.settings.db), 
            'queues': list(allqueues['queues']),
            'count': len(allqueues['queues'])}
        self.write("%s\n" % cyclone.escape.json_encode(stats))
        self.finish()

class XmlrpcHandler(cyclone.web.XmlrpcRequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def xmlrpc_get(self, queue):
        try:
            value = yield self.settings.oper.queue_get(queue.encode("utf-8"))
        except Exception, e:
            raise cyclone.web.HTTPError(400, e)

        if value:
            defer.returnValue(value)
        else:
            raise cyclone.web.HTTPError(404)

    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def xmlrpc_set(self, queue, value):
        try:
            result = yield self.settings.oper.queue_add(queue.encode("utf-8"), value.encode("utf-8"))
        except Exception, e:
            raise cyclone.web.HTTPError(404, e)

        defer.returnValue(result)

class RestQueueHandler(cyclone.web.RequestHandler):
    """ RestQueueHandler applies HTTP Methods to a given queue.
        GET gets an object out of the queue.
        POST inserts an object in the queue (I know, it could be PUT)
        DELETE is a TODO yet. Once you get the object, it's deleted for good.
    """
    def get(self, queue):
        self.write('queue %s'% queue)
    
    def post(self, queue):
        self.write('queue %s' % queue)

class QueueHandler(cyclone.web.RequestHandler):
    """ QueueHandler deals with the json protocol"""

    def get(self):
        self.redirect("/static/help.html")
    
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def post(self):
        body = self.get_argument('body')
        try:
            jsonbody = cyclone.escape.json_decode(body)
            cmd = jsonbody["cmd"]
            assert cmd
        except:
            raise cyclone.web.HTTPError(400, 'Malformed json. Invalid format.')
        
        d = CommandDispatch(self.settings.oper)
        r = yield d.execute(cmd, jsonbody)
        if r:
            self.write(r) 
        else:
            self.write(cyclone.escape.json_encode({"Error":"Null resultset"}))

        self.finish()

class CometQueueHandler(cyclone.web.RequestHandler):
    """
        CometQueueHandler is a permanent consumer for objects in a queue.
        it must only feed new objects to a permanent http connection
        deletion is not handled here for now.
        As each queue object has its own key, it can be done thru /queue interface
    """
    def _disconnected(self, why, handler):
        try:
            self.settings.comet.presence.pop(handler)
        except:
            pass

    #TODO: do it right
    @cyclone.web.asynchronous
    def get(self, queue):
        """
            this method is meant only as a light http consumer, with no delete
            simple test: point the browser to /c/test
            execute python engine.py -p, check the browser to see if the object appears, 
            then execute engine.py -c again, to make another object appear in the browser.
            The main reasoning is that this method should not remove objects from the queue, neither 
            show objects with reference counter > 1.
            It can be changed by removing softget=True from oper_get request. This way, it will be truly a http consumer.
        """
        self.set_header("Content-Type", "text/plain")
        self.settings.comet.presence[self] = queue.encode("utf-8")
        self.notifyFinish().addCallback(self._disconnected, self)
        self.write("comet:\n")
        self.flush()


class CometDispatcher(object):
    def __init__(self, oper):
        self.oper = oper
        self.presence={} # TODO: could use redis itself to hold user presence
        self.task = task.LoopingCall(self.dispatch)
        self.task.start(1)

    @defer.inlineCallbacks
    def dispatch(self):
        for handler, queue in self.presence.items():
            # softget= True, so it wont disrupt the queue order
            # TODO: cache results so it wont mess up with a lot of clients/queues
            value = yield self.oper.queue_get(queue, softget=True)            
            if value:
                handler.write('%s\n' % value)
                handler.flush()
        defer.returnValue(None)


class RestMQ(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/",       IndexHandler),
            (r"/q/(.*)", RestQueueHandler),
            (r"/c/(.*)", CometQueueHandler),
            (r"/stats",  StatusHandler),
            (r"/xmlrpc", XmlrpcHandler),
            (r"/queue",  QueueHandler)
        ]
        db = txredis.lazyRedisConnectionPool()
        oper = engine.RedisOperations(db)
        settings = {
            "db": db,
            "comet": CometDispatcher(oper),
            "static_path": "./static",
            "oper": oper,
        }

        cyclone.web.Application.__init__(self, handlers, **settings)

application = service.Application("restmq")
srv = internet.TCPServer(8888, RestMQ())
srv.setServiceParent(application)
