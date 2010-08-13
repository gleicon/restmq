# coding: utf-8

import types
import os.path
import txredisapi
import cyclone.web
import cyclone.escape
from restmq import core
from restmq import dispatch
from collections import defaultdict
from twisted.python import log
from twisted.internet import task, defer


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
    @cyclone.web.asynchronous
    def get(self):
        queue = self.get_argument("queue", None)
        callback = self.get_argument("callback", None)
        if queue == None:
            self.render('basic_routes.html')
            return
        try:
            policy, value = yield self.settings.oper.queue_get(queue)
            assert value
        except Exception, e:
            raise cyclone.web.HTTPError(404, str(e))

        CustomHandler(self, callback).finish(value)

    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def post(self):
        queue = self.get_argument("queue").encode('utf-8')
        value = self.get_argument("value")
        callback = self.get_argument("callback", None)
        try:
            result = yield self.settings.oper.queue_add(queue, value)
        except Exception, e:
            raise cyclone.web.HTTPError(400, str(e))
        
        self.settings.comet.queue.put(queue)
        CustomHandler(self, callback).finish(result)


class RestQueueHandler(cyclone.web.RequestHandler):
    """ 
        RestQueueHandler applies HTTP Methods to a given queue.
        GET /q/queuename gets an object out of the queue.
        POST /q/queuename inserts an object in the queue (I know, it could be PUT). The payload comes in the parameter body
        DELETE method purgue and delete the queue. it might disconnect all consumers (comet)
    """
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self, queue):
        callback = self.get_argument("callback", None)

        if queue == None or queue=="":
            allqueues = yield self.settings.oper.queue_all()
            self.render("list_queues.html", route="q", extended_route="REST", allqueues=allqueues['queues'])
            return
        try:
            policy, value = yield self.settings.oper.queue_get(queue)
            assert value
        except Exception, e:
            raise cyclone.web.HTTPError(404, str(e))
        
        CustomHandler(self, callback).finish(value)
    
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def post(self, queue):
        value = self.get_argument("value")
        callback = self.get_argument("callback", None)
        try:
            result = yield self.settings.oper.queue_add(queue, value)
        except Exception, e:
            raise cyclone.web.HTTPError(400, str(e))

        self.settings.comet.queue.put(queue)
        CustomHandler(self, callback).finish(result)
    
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def delete(self, queue):
        callback = self.get_argument("callback", None)
        clients = self.settings.comet.presence.get(queue, [])
        for c in clients:
            try:
                c.finish()
            except:
                pass
        try:
            ret = yield self.settings.oper.queue_purgue(queue)
        except:
            ret='Error: Queue was not purged'
        CustomHandler(self, callback).finish(ret)


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
            r = cyclone.escape.json_encode({"error":"null resultset"})

        self.finish(r)


class CometQueueHandler(cyclone.web.RequestHandler):
    """
        CometQueueHandler is a permanent consumer for objects in a queue.
        it must only feed new objects to a permanent http connection
        deletion is not handled here for now.
        As each queue object has its own key, it can be done thru /queue interface
    """
    def _disconnected(self, why, handler, queue_name):
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
        queue_name = queue.encode("utf-8")
        self.settings.comet.presence[queue_name].append(handler)
        self.notifyFinish().addCallback(self._disconnected, handler, queue_name)


class PolicyQueueHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self, queue):
        callback = self.get_argument("callback", None)
        try:
            policy = yield self.settings.oper.queue_policy_get(queue)
        except Exception, e:
            raise cyclone.web.HTTPError(404, str(e))

        CustomHandler(self, callback).finish(policy)

    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def post(self, queue):
        policy = self.get_argument("policy")
        callback = self.get_argument("callback", None)
        try:
            result = yield self.settings.oper.queue_policy_set(queue, policy)
        except Exception, e:
            raise cyclone.web.HTTPError(400, "Error posting %s" % str(e))

        CustomHandler(self, callback).finish(result)


class JobQueueInfoHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self, queue):
        try:
            jobs = yield self.settings.oper.queue_last_items(queue)
            job_count = yield self.settings.oper.queue_len(queue)
            queue_obj_count = yield self.settings.oper.queue_count_elements(queue)
            self.render("jobs.html", queue=queue, jobs=jobs, job_count=job_count, queue_size=queue_obj_count)
        except Exception, e:
            log.msg("cannot get data: %s" % str(e))
            raise cyclone.web.HTTPError(400, str(e))


class StatusHandler(cyclone.web.RequestHandler):
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self, queue):
        # application/json or text/json ? 
        self.set_header("Content-Type", "text/plain")
        if queue == None or len(queue) < 1:
            allqueues = yield self.settings.oper.queue_all()
            stats={'redis': repr(self.settings.db), 
                'queues': list(allqueues['queues']),
                'count': len(allqueues['queues'])}
            self.finish("%s\n" % cyclone.escape.json_encode(stats))
        else:
            qlen = yield self.settings.oper.queue_len(queue)
            stats={'redis': repr(self.settings.db), 
                'queue': queue,
                'len': qlen}
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
        keys = self.qcounter.keys()
        for queue_name in keys:
            if not self.presence.has_key(queue_name):
                self.qcounter.pop(queue_name)

    def _auto_dispatch(self):
        for queue_name, handlers in self.presence.items():
            self.dispatch(queue_name, handlers)

    @defer.inlineCallbacks
    def dispatch(self, queue_name, handlers=None):
        qstat = yield self.oper.queue_status(queue_name)
        if qstat['status'] != self.oper.STARTQUEUE:
            return
        handlers = handlers or self.presence.get(queue_name)
        if handlers:
            size = len(handlers)
            try:
                policy, contents = yield self.oper.queue_tail(queue_name, delete_obj=True) # change it to false to preserve objects
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
                    log.msg("cannot dump to comet client: %s" % str(e))


class QueueControlHandler(cyclone.web.RequestHandler):
    """ QueueControlHandler stops/starts a queue (pause consumers)"""

    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def get(self, queue):
        self.set_header("Content-Type", "text/plain")
        stats={}
        if queue == None or len(queue) < 1:
            allqueues = yield self.settings.oper.queue_all()
            aq={}
            for q in allqueues:
                aq[q]=yield self.settings.oper.queue_status(q)
    
            stats={'redis': repr(self.settings.db), 
                'queues': aq,
                'count': len(aq)}
        else:
            qstat = yield self.settings.oper.queue_status(queue)
            stats={'redis': repr(self.settings.db), 
                'queue': queue,
                'status': qstat}

        self.finish("%s\n" % cyclone.escape.json_encode(stats))
    
    @defer.inlineCallbacks
    @cyclone.web.asynchronous
    def post(self, queue):
        status = self.get_argument("status", None)
        if status == 'start':
            qstat = yield self.settings.oper.queue_changestatus(queue, self.settings.oper.STARTQUEUE)
        elif status =='stop':
            qstat = yield self.settings.oper.queue_changestatus(queue, self.settings.oper.STOPQUEUE)
        else:
            qstat = 'invalid status: %s' % status

        self.finish("%s\n" % cyclone.escape.json_encode({'stat':qstat}))

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
        log.msg("connection made: %s" % queue)
        self.queue = queue
        handler = CustomHandler(self, None)
        queue_name = queue.encode("utf-8")
        self.settings.comet.presence[queue_name].append(handler)
        self.notifyFinish().addCallback(self._disconnected, handler, queue_name)

    def connectionLost(self, why):
        log.msg("connection lost:", why)

    def messageReceived(self, message):
        """
            same idea as COMET consumer, but using websockets. how cool is that ?
        """
        print "msg recv: %s" % message
        self.sendMessage(message)

class Application(cyclone.web.Application):
    def __init__(self):
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

        db = txredisapi.lazyRedisConnectionPool(pool_size=10)
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
