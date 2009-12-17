# coding: utf-8

import types
import txredisapi
import cyclone.web
import cyclone.escape
from restmq import core
from restmq import dispatch
from collections import defaultdict
from twisted.python import log
from twisted.internet import task, defer


class IndexHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self):
        queue = self.get_argument("queue")
        try:
            policy, value = yield self.settings.oper.queue_get(queue)
            assert value
        except Exception, e:
            raise cyclone.web.HTTPError(404, str(e))
        
        self.finish("get: %s\n" % repr(value))

    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def post(self):
        queue = self.get_argument("queue")
        value = self.get_argument("value")
        try:
            result = yield self.settings.oper.queue_add(queue, value)
        except Exception, e:
            raise cyclone.web.HTTPError(400, str(e))
        
        self.settings.comet.queue.put(queue)
        self.finish("set: %s\n" % result)


class RestQueueHandler(cyclone.web.RequestHandler):
    """ 
        RestQueueHandler applies HTTP Methods to a given queue.
        GET /q/queuename gets an object out of the queue.
        POST /q/queuename inserts an object in the queue (I know, it could be PUT). The payload comes in the parameter body
        DELETE method is undefined. Once you get the object, it's deleted for good.
    """
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self, queue):
        try:
            policy, value = yield self.settings.oper.queue_get(queue)
            assert value
        except Exception, e:
            raise cyclone.web.HTTPError(404, str(e))
        
        self.finish("get: %s\n" % repr(value))
    
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def post(self, queue):
        body = self.get_argument("value")
        try:
            result = yield self.settings.oper.queue_add(queue, value)
        except Exception, e:
            raise cyclone.web.HTTPError(400, str(e))

        self.settings.comet.queue.put(queue)
        self.finish("set: %s\n" % result)


class XmlrpcHandler(cyclone.web.XmlrpcRequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def xmlrpc_get(self, queue):
        try:
            policy, value = yield self.settings.oper.queue_get(queue)
            assert value
        except Exception, e:
            raise cyclone.web.HTTPError(404, str(e))
        defer.returnValue(value)

    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def xmlrpc_set(self, queue, value):
        try:
            result = yield self.settings.oper.queue_add(queue, value)
        except Exception, e:
            raise cyclone.web.HTTPError(400, e)
        self.settings.comet.queue.put(queue)
        defer.returnValue(result)


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
        if not r:
            r = cyclone.escape.json_encode({"Error":"Null resultset"})

        self.finish(r)


class CometQueueHandler(cyclone.web.RequestHandler):
    """
        CometQueueHandler is a permanent consumer for objects in a queue.
        it must only feed new objects to a permanent http connection
        deletion is not handled here for now.
        As each queue object has its own key, it can be done thru /queue interface
    """
    def _disconnected(self, why, queue_name):
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


class PolicyQueueHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self, queue):
        try:
            policy = yield self.settings.oper.queue_policy_get(queue)
        except Exception, e:
            raise cyclone.web.HTTPError(404, str(e))

        self.finish(policy)

    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def post(self, queue):
        policy = self.get_argument("policy")
        try:
            result = yield self.settings.oper.queue_policy_set(queue, policy)
        except Exception, e:
            raise cyclone.web.HTTPError(400, str(e))

        self.finish(result)


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
        self.finish("%s\n" % cyclone.escape.json_encode(stats))


class CometDispatcher(object):
    def __init__(self, oper):
        self.oper = oper
        self.queue = defer.DeferredQueue()
        self.presence = defaultdict(lambda: [])
        self.qcounter = defaultdict(lambda: 0)
        self.queue.get().addCallback(self._new_data)
        task.LoopingCall(self._auto_dispatch).start(1) # secs between checkings
        task.LoopingCall(self._counters_cleanup).start(30)

    def _new_data(self, queue_name):
        self.dispatch(queue_name)
        self.queue.get().addCallback(self._new_data)

    def _counters_cleanup(self):
        for queue_name in self.qcounter:
            if not self.presence.has_key(queue_name):
                self.qcounter.pop(queue_name)

    def _auto_dispatch(self):
        for queue_name, handlers in self.presence.items():
            self.dispatch(queue_name, handlers)

    @defer.inlineCallbacks
    def dispatch(self, queue_name, handlers=None):
        handlers = handlers or self.presence.get(queue_name)
        if handlers:
            size = len(handlers)
            try:
                policy, contents = yield self.oper.queue_tail(queue_name)
                assert policy and contents and isinstance(contents, types.ListType)
            except:
                defer.returnValue(None)

            if policy == core.POLICY_BROADCAST:
                self._dump(handlers, contents)

            elif policy == core.POLICY_ROUNDROBIN:
                idx = self.qcounter[queue_name] % size
                self._dump((handlers[idx],), contents)
                self.qcounter[queue_name] += 1
        
    def _dump(self, handlers, contents):
        for handler in handlers:
            for content in contents:
                try:
                    handler.write("%s\n" % cyclone.escape.json_encode(content))
                    handler.flush()
                except Exception, e:
                    log.write("cannot dump to comet client: %s" % str(e))


class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/",       IndexHandler),
            (r"/q/(.*)", RestQueueHandler),
            (r"/c/(.*)", CometQueueHandler),
            (r"/p/(.*)", PolicyQueueHandler),
            (r"/xmlrpc", XmlrpcHandler),
            (r"/stats",  StatusHandler),
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
