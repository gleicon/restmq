# coding: utf-8

import types
import os.path
import cyclone.web
import cyclone.redis
import cyclone.escape
from collections import defaultdict
from twisted.python import log
from twisted.internet import task, defer

from restmq import core
from restmq import dispatch


class CustomHandler(object):
    def __init__(self, handler, json_callback=None):
        self.handler = handler
        self.json_callback = json_callback

    def write(self, text):
        if not isinstance(text, types.StringType):
            text = cyclone.escape.json_encode(text)

        if isinstance(self.handler, cyclone.web.WebSocketHandler):
            self.handler.sendMessage(text)
        else:
            if self.json_callback:
                self.handler.write("%s(%s);\r\n" % (self.json_callback, text))
            else:
                self.handler.write(text+"\r\n")

    def flush(self):
        self.handler.flush()

    def finish(self, text=None):
        if buffer:
            self.write(text)
        self.handler.finish()


class IndexHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    def get(self):
        queue = self.get_argument("queue", None)
        callback = self.get_argument("callback", None)

        if queue is None:
            self.render("basic_routes.html")
            defer.returnValue(None)

        try:
            policy, value = yield self.settings.oper.queue_get(queue)
        except Exception, e:
            log.msg("ERROR: oper.queue_get('%s') failed: %s" % (queue, e))
            cyclone.web.HTTPError(503)

        if value:
            CustomHandler(self, callback).finish(value)
        else:
            raise cyclone.web.HTTPError(404)


    @defer.inlineCallbacks
    def post(self):
        queue = self.get_argument("queue")
        value = self.get_argument("value")
        callback = self.get_argument("callback", None)

        try:
            result = yield self.settings.oper.queue_add(queue, value)
        except Exception, e:
            log.msg("ERROR: oper.queue_add('%s', '%s') failed: %s" % (queue, value))
            raise cyclone.web.HTTPError(503)

        if result:
            self.settings.comet.queue.put(queue)
            CustomHandler(self, callback).finish(result)
        else:
            raise cyclone.web.HTTPError(400)


class RestQueueHandler(cyclone.web.RequestHandler):
    """ 
        RestQueueHandler applies HTTP Methods to a given queue.
        GET /q/queuename gets an object out of the queue.
        POST /q/queuename inserts an object in the queue (I know, it could be PUT). The payload comes in the parameter body
        DELETE method purge and delete the queue. It will close all comet connections.
    """
    @defer.inlineCallbacks
    def get(self, queue):
        callback = self.get_argument("callback", None)

        if queue:
            try:
                policy, value = yield self.settings.oper.queue_get(queue)
            except Exception, e:
                log.msg("ERROR: oper.queue_get('%s') failed: %s" % (queue, e))
                raise cyclone.web.HTTPError(503)

            CustomHandler(self, callback).finish(value)
        else:
            try:
                allqueues = yield self.settings.oper.queue_all()
            except Exception, e:
                log.msg("ERROR: oper.queue_all() failed: %s" % e)
                raise cyclone.web.HTTPError(503)

            self.render("list_queues.html", route="q", extended_route="REST", allqueues=allqueues["queues"])

    @defer.inlineCallbacks
    def post(self, queue):
        value = self.get_argument("value")
        callback = self.get_argument("callback", None)

        try:
            result = yield self.settings.oper.queue_add(queue, value)
        except Exception, e:
            log.msg("ERROR: oper.queue_add('%s', '%s') failed: %s" % (queue, value))
            raise cyclone.web.HTTPError(503)

        if result:
            self.settings.comet.queue.put(queue)
            CustomHandler(self, callback).finish(result)
        else:
            raise cyclone.web.HTTPError(400)

    @defer.inlineCallbacks
    def delete(self, queue):
        callback = self.get_argument("callback", None)
        clients = self.settings.comet.presence.get(queue, [])

        for conn in clients:
            try:
                conn.finish()
            except Exception, e:
                log.msg("ERROR: cannot close client connection: %s = %s" % (conn, e))

        try:
            result = yield self.settings.oper.queue_purge(queue)
        except Exception, e:
            log.msg("ERROR: oper.queue_purge('%s') failed: %s" % (queue, e))
            raise cyclone.web.HTTPError(503)

        CustomHandler(self, callback).finish(result)


class QueueHandler(cyclone.web.RequestHandler):
    """ QueueHandler deals with the json protocol"""

    def get(self):
        self.redirect("/static/help.html")
    
    @defer.inlineCallbacks
    def post(self):
        msg = self.get_argument("msg", None)
        body = self.get_argument("body", None)

        if msg is None and body is None:
            raise cyclone.web.HTTPError(400)

        try:
            jsonbody = cyclone.escape.json_decode(msg or body)
            cmd = jsonbody["cmd"]
            assert cmd
        except:
            raise cyclone.web.HTTPError(400, "Malformed JSON. Invalid format.")
        
        try:
            result = yield dispatch.CommandDispatch(self.settings.oper).execute(cmd, jsonbody)
        except Exception, e:
            log.msg("ERROR: CommandDispatch/oper.%s('%s') failed: %s" % (cmd, jsonbody, e))
            raise cyclone.web.HTTPError(503)

        if result:
            self.finish(result)
        else:
            self.finish(cyclone.escape.json_encode({"error":"null resultset"}))


class CometQueueHandler(cyclone.web.RequestHandler):
    """
        CometQueueHandler is a permanent consumer for objects in a queue.
        it must only feed new objects to a permanent http connection
        deletion is not handled here for now.
        As each queue object has its own key, it can be done thru /queue interface
    """
    def _on_disconnect(self, why, handler, queue_name):
        try:
            self.settings.comet.presence[queue_name].remove(handler)
            if not len(self.settings.comet.presence[queue_name]):
                self.settings.comet.presence.pop(queue_name)
        except:
            pass

    @cyclone.web.asynchronous
    def get(self, queue):
        """
            this method is meant to build light http consumers emulating a subscription
            simple test: point the browser to /c/test
            execute python engine.py -p, check the browser to see if the object appears, 
            then execute engine.py -c again, to make another object appear in the browser.
            Not it deletes objects from redis. To change it, set getdel to False on CometDispatcher 
        """

        self.set_header("Content-Type", "text/plain")
        callback = self.get_argument("callback", None)

        handler = CustomHandler(self, callback)

        try:
            queue_name = queue.encode("utf-8")
        except:
            raise cyclone.web.HTTPError(400, "Invalid Queue Name")

        self.settings.comet.presence[queue_name].append(handler)
        self.notifyFinish().addCallback(self._on_disconnect, handler, queue_name)


class PolicyQueueHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    def get(self, queue):
        callback = self.get_argument("callback", None)

        try:
            policy = yield self.settings.oper.queue_policy_get(queue)
        except Exception, e:
            log.msg("ERROR: oper.queue_policy_get('%s') failed: %s" % (queue, e))
            raise cyclone.web.HTTPError(503)

        CustomHandler(self, callback).finish(policy)

    @defer.inlineCallbacks
    def post(self, queue):
        policy = self.get_argument("policy")
        callback = self.get_argument("callback", None)

        try:
            result = yield self.settings.oper.queue_policy_set(queue, policy)
        except Exception, e:
            log.msg("ERROR: oper.queue_policy_set('%s', '%s') failed: %s" % (queue, policy, e))
            raise cyclone.web.HTTPError(503)

        CustomHandler(self, callback).finish(result)


class JobQueueInfoHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    def get(self, queue):
        try:
            jobs = yield self.settings.oper.queue_last_items(queue)
            job_count = yield self.settings.oper.queue_len(queue)
            queue_obj_count = yield self.settings.oper.queue_count_elements(queue)
        except Exception, e:
            log.msg("ERROR: Cannot get JOB data: queue=%s, %s" % (queue, e))
            raise cyclone.web.HTTPError(503)

        self.render("jobs.html", queue=queue, jobs=jobs, job_count=job_count, queue_size=queue_obj_count)


class StatusHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    def get(self, queue):
        # application/json or text/json ? 
        self.set_header("Content-Type", "text/plain")

        if queue is None or len(queue) < 1:
            try:
                allqueues = yield self.settings.oper.queue_all()
            except Exception, e:
                log.msg("ERROR: oper.queue_all() failed: %s" % e)
                raise cyclone.web.HTTPError(503)

            self.finish("%s\r\n" % cyclone.escape.json_encode({
                "redis": repr(self.settings.db), 
                "queues": list(allqueues["queues"]),
                "count": len(allqueues["queues"])}))
        else:
            try:
                qlen = yield self.settings.oper.queue_len(queue)
            except Exception, e:
                log.msg("ERROR: oper.queue_len('%s') failed: %s" % (queue, e))
                raise cyclone.web.HTTPError(503)

            self.finish("%s\r\n" % cyclone.escape.json_encode({
                "redis": repr(self.settings.db), 
                "queue": queue, "len": qlen}))


class CometDispatcher(object):
    def __init__(self, oper, del_obj=True):
        self.oper = oper
        self.queue = defer.DeferredQueue()
        self.presence = defaultdict(lambda: [])
        self.qcounter = defaultdict(lambda: 0)
        self.queue.get().addCallback(self._new_data)
        task.LoopingCall(self._auto_dispatch).start(1) # secs between checkings
        task.LoopingCall(self._counters_cleanup).start(30) # presence maintenance
        self.delete_objects = del_obj

    def _new_data(self, queue_name):
        self.dispatch(queue_name)
        self.queue.get().addCallback(self._new_data)

    def _auto_dispatch(self):
        for queue_name, handlers in self.presence.items():
            self.dispatch(queue_name, handlers)

    def _counters_cleanup(self):
        keys = self.qcounter.keys()
        for queue_name in keys:
            if not self.presence.has_key(queue_name):
                self.qcounter.pop(queue_name)

    @defer.inlineCallbacks
    def dispatch(self, queue_name, handlers=None):
        try:
            qstat = yield self.oper.queue_status(queue_name)
        except Exception, e:
            log.msg("ERROR: oper.queue_status('%s') failed: %s" % (queue_name, e))
            defer.returnValue(None)

        if qstat["status"] != self.oper.STARTQUEUE:
            defer.returnValue(None)

        handlers = handlers or self.presence.get(queue_name)
        if handlers:
            size = len(handlers)
            try:
                policy, contents = yield self.oper.queue_tail(queue_name, delete_obj = self.delete_objects)
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
                    handler.write(cyclone.escape.json_encode(content))
                    handler.flush()
                except Exception, e:
                    log.msg("ERROR: Cannot write to comet client: %s = %s" % (handler, e))


class QueueControlHandler(cyclone.web.RequestHandler):
    """ QueueControlHandler stops/starts a queue (pause consumers)"""

    @defer.inlineCallbacks
    def get(self, queue):
        self.set_header("Content-Type", "text/plain")

        stats={}
        if queue:
            try:
                qstat = yield self.settings.oper.queue_status(queue)
            except Exception, e:
                log.msg("ERROR: oper.queue_status('%s') failed: %s" % (queue, e))
                raise cyclone.web.HTTPError(503)

            stats={"redis": repr(self.settings.db), "queue": queue, "status": qstat}

        else:
            try:
                allqueues = yield self.settings.oper.queue_all()
            except Exception, e:
                log.msg("ERROR: oper.queue_all() failed: %s" % e)
                raise cyclone.web.HTTPError(503)

            aq={}
            for q in allqueues:
                try:
                    aq[q] = yield self.settings.oper.queue_status(q)
                except Exception, e:
                    log.msg("ERROR: oper.queue_status('%s') failed: %s" % (q, e))
                    raise cyclone.web.HTTPError(503)
    
            stats={"redis": repr(self.settings.db), "queues": aq, "count": len(aq)}

        self.finish("%s\r\n" % cyclone.escape.json_encode(stats))
    
    @defer.inlineCallbacks
    def post(self, queue):
        status = self.get_argument("status", None)

        if status == "start":
            try:
                qstat = yield self.settings.oper.queue_changestatus(queue, self.settings.oper.STARTQUEUE)
            except Exception, e:
                log.msg("ERROR: oper.queue_changestatus('%s', STARTQUEUE) failed: %s" % (queue, e))
                raise cyclone.web.HTTPError(503)

        elif status == "stop":
            try:
                qstat = yield self.settings.oper.queue_changestatus(queue, self.settings.oper.STOPQUEUE)
            except Exception, e:
                log.msg("ERROR: oper.queue_changestatus('%s', STOPQUEUE) failed: %s" % (queue, e))
                raise cyclone.web.HTTPError(503)

        else:
            qstat = "invalid status: %s" % status

        self.finish("%s\r\n" % cyclone.escape.json_encode({'stat':qstat}))


class WebSocketQueueHandler(cyclone.web.WebSocketHandler):
    """
        Guess what, I had a fever, and the only prescription is websocket
    """
    def _disconnected(self, why, handler, queue_name):
        try:
            self.settings.comet.presence[queue_name].remove(handler)
            if not len(self.settings.comet.presence[queue_name]):
                self.settings.comet.presence.pop(queue_name)
        except:
            pass
    
    def connectionMade(self, queue):
        self.queue = queue
        handler = CustomHandler(self, None)

        try:
            queue_name = queue.encode("utf-8")
        except:
            raise cyclone.web.HTTPError(400, "Invalid Queue Name")

        self.settings.comet.presence[queue_name].append(handler)
        self.notifyFinish().addCallback(self._disconnected, handler, queue_name)

    def messageReceived(self, message):
        """
            same idea as COMET consumer, but using websockets. how cool is that ?
        """
        self.sendMessage(message)


class Application(cyclone.web.Application):
    def __init__(self, redis_host, redis_port, redis_pool):
        handlers = [
            (r"/",       IndexHandler),
            (r"/q/(.*)", RestQueueHandler),
            (r"/c/(.*)", CometQueueHandler),
            (r"/p/(.*)", PolicyQueueHandler),
            (r"/j/(.*)", JobQueueInfoHandler),
            (r"/stats/(.*)",  StatusHandler),
            (r"/queue",  QueueHandler),
            (r"/control/(.*)",  QueueControlHandler),
            (r"/ws/(.*)",  WebSocketQueueHandler),
        ]

        db = cyclone.redis.lazyRedisConnectionPool(redis_host, redis_port, pool_size=redis_pool)
        oper = core.RedisOperations(db)
        cwd = os.path.dirname(__file__)

        settings = {
            "db": db,
            "oper": oper,
            "comet": CometDispatcher(oper),
            "static_path": os.path.join(cwd, "static"),
            "template_path": os.path.join(cwd, "templates"),
        }

        cyclone.web.Application.__init__(self, handlers, **settings)
