# coding: utf-8

import txredisapi
import cyclone.web
import cyclone.escape
from restmq import core
from restmq import dispatch
from collections import defaultdict
from twisted.internet import task, defer


class IndexHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self):
        queue = self.get_argument("queue")
        try:
            policy, value = yield self.settings.oper.queue_get(queue.encode("utf-8"))
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
            policy, value = yield self.settings.oper.queue_get(queue.encode("utf-8"))
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
    """ 
        RestQueueHandler applies HTTP Methods to a given queue.
        GET /q/queuename gets an object out of the queue.
        POST /q/queuename inserts an object in the queue (I know, it could be PUT). The payload comes in the parameter body
        DELETE method is undefined. Once you get the object, it's deleted for good.
    """
    @defer.inlineCallbacks
    def get(self, queue):
        try:
            policy, value = yield self.settings.oper.queue_get(queue.encode("utf-8"))
        except Exception, e:
            self.write("exception get: %s\n" % str(e))
        else:
            self.write("get: %s\n" % repr(value))
        self.finish()
    
    @defer.inlineCallbacks
    def post(self, queue):
        body = self.get_argument("value")
        try:
            result = yield self.settings.oper.queue_add(queue.encode("utf-8"), value.encode("utf-8"))
        except Exception, e:
            self.write("set failed: %s\n" % str(e))
        else:
            self.write("set: %s\n" % result)
        self.finish()


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
        
        d = dispatch.CommandDispatch(self.settings.oper)
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
    def _disconnected(self, why, handler, queue_name):
        try:
            self.settings.comet.presence[queue_name].remove(self)
            if not len(self.settings.comet.presence[queue_name]):
                self.settings.comet.presence.pop(queue_name)
        except:
            pass

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
        queue_name = queue.encode("utf-8")
        self.settings.comet.presence[queue_name].append(self)
        self.notifyFinish().addCallback(self._disconnected, queue_name)
        self.flush()


class CometDispatcher(object):
    def __init__(self, oper):
        self.oper = oper
        self.presence = defaultdict(lambda: [])
        self.qcounter = defaultdict(lambda: 0)
        self.task = task.LoopingCall(self.dispatch)
        self.task.start(1)

    @defer.inlineCallbacks
    def dispatch(self):
        for queue_name, handlers in self.presence.items():
            policy, content = yield self.oper.queue_get(queue_name)

            if policy == something.BROADCAST:
                self._dump(handlers, content)

            elif policy == something.ROUNDROBIN:
                idx = self.qcounter[queue_name] % len(handlers)
                self._dump((handlers[idx],), content)
                self.qcounter[queue_name] += 1
        defer.returnValue(None)

    def _dump(self, handlers, content):
        for handler in handlers:
            handler.write("%s\n" % content)
            handler.flush()

class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/",       IndexHandler),
            (r"/q/(.*)", RestQueueHandler),
            (r"/c/(.*)", CometQueueHandler),
            (r"/stats",  StatusHandler),
            (r"/xmlrpc", XmlrpcHandler),
            (r"/queue",  QueueHandler)
        ]
        db = txredisapi.lazyRedisConnectionPool()
        oper = core.RedisOperations(db)
        settings = {
            "db": db,
            "comet": CometDispatcher(oper),
            "static_path": "./static",
            "oper": oper,
        }

        cyclone.web.Application.__init__(self, handlers, **settings)
