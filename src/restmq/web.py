# coding: utf-8

from os.path import dirname, abspath, join
import types
import base64
import hashlib
import os.path
import functools
import cyclone.web
import cyclone.redis
import cyclone.escape
import cyclone.websocket

from collections import defaultdict
from ConfigParser import ConfigParser

from twisted.python import log
from twisted.internet import task, defer, reactor

import pkg_resources as pkg

from restmq import core
from restmq import dispatch

class InvalidAddress(Exception):
    pass

class InvalidPassword(Exception):
    pass

def authorize(category):
    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            try:
                self.settings.acl.apply(self, category)
            except InvalidAddress:
                raise cyclone.web.HTTPError(401)
            except InvalidPassword:
                raise cyclone.web.HTTPAuthenticationRequired("Basic", "RestMQ Restricted Access")
            else:
                return method(self, *args, **kwargs)
        return wrapper
    return decorator


class CustomHandler(object):
    def __init__(self, handler, json_callback=None):
        self.handler = handler
        self.json_callback = json_callback

    def write(self, text):
        if not isinstance(text, types.StringType):
            text = cyclone.escape.json_encode(text)

        if isinstance(self.handler, cyclone.websocket.WebSocketHandler):
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
    @authorize("rest_consumer")
    @defer.inlineCallbacks
    def get(self):
        try:
            queue = self.get_argument("queue", None)
            callback = self.get_argument("callback", None)
            if queue is None:
                self.redirect("/static/index.html")
                defer.returnValue(None)
        except Exception, e:
            print e

        try:
            policy, value = yield self.settings.oper.queue_get(queue)
        except Exception, e:
            log.msg("ERROR: oper.queue_get('%s') failed: %s" % (queue, e))
            cyclone.web.HTTPError(503)

        if value:
            CustomHandler(self, callback).finish(value)
        else:
            raise cyclone.web.HTTPError(404)

    @authorize("rest_producer")
    @defer.inlineCallbacks
    def post(self):
        queue = self.get_argument("queue")
        msg = self.get_argument("msg", None)
        value = self.get_argument("value", None)
        ttl = self.get_argument("ttl", None)

        if msg is None and value is None:
            raise cyclone.web.HTTPError(400)
        callback = self.get_argument("callback", None)

        try:
            result = yield self.settings.oper.queue_add(queue, value, ttl=ttl)
        except Exception, e:
            log.msg("ERROR: oper.queue_add('%s', '%s') failed: %s" % (queue, value, e))
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
    @authorize("rest_consumer")
    @defer.inlineCallbacks
    def get(self, queue):
        callback = self.get_argument("callback", None)

        if queue:
            try:
                policy, value = yield self.settings.oper.queue_get(queue)
            except Exception, e:
                log.msg("ERROR: oper.queue_get('%s') failed: %s" % (queue, e))
                raise cyclone.web.HTTPError(503)

            if value is None: raise cyclone.web.HTTPError(204)
            CustomHandler(self, callback).finish(value)
        else:
            try:
                allqueues = yield self.settings.oper.queue_all()
            except Exception, e:
                log.msg("ERROR: oper.queue_all() failed: %s" % e)
                raise cyclone.web.HTTPError(503)

            self.render("list_queues.html", route="q", extended_route="REST", allqueues=allqueues["queues"])

    @authorize("rest_producer")
    @defer.inlineCallbacks
    def post(self, queue):
        msg = self.get_argument("msg", None)
        value = self.get_argument("value", None)
        ttl = self.get_argument("ttl", None)
        if msg is None and value is None:
            raise cyclone.web.HTTPError(400)
        callback = self.get_argument("callback", None)

        try:
            result = yield self.settings.oper.queue_add(queue, msg or value, ttl=ttl)
        except Exception, e:
            log.msg("ERROR: oper.queue_add('%s', '%s') failed: %s" % (queue, msg or value, e))
            raise cyclone.web.HTTPError(503)

        if result:
            self.settings.comet.queue.put(queue)
            CustomHandler(self, callback).finish(result)
        else:
            raise cyclone.web.HTTPError(400)

    @authorize("rest_producer")
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

    @authorize("rest_producer")
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

    @authorize("comet_consumer")
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
    @authorize("rest_consumer")
    @defer.inlineCallbacks
    def get(self, queue):
        callback = self.get_argument("callback", None)

        try:
            policy = yield self.settings.oper.queue_policy_get(queue)
        except Exception, e:
            log.msg("ERROR: oper.queue_policy_get('%s') failed: %s" % (queue, e))
            raise cyclone.web.HTTPError(503)
        r = {'queue':queue, 'value': self.inverted_policies.get(policy, "unknown")}
        CustomHandler(self, callback).finish(r)

    @authorize("rest_producer")
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
    @authorize("rest_consumer")
    @defer.inlineCallbacks
    def get(self, queue):
        self.set_header("Content-Type", "application/json")
        jsoncallback = self.get_argument("callback", None)
        res = {}

        if queue is None or len(queue) < 1:
            try:
                allqueues = yield self.settings.oper.queue_all()
            except Exception, e:
                log.msg("ERROR: oper.queue_all() failed: %s" % e)
                raise cyclone.web.HTTPError(503)
            ql = list(allqueues["queues"]) 
            res["queues"]={}
            for q in ql:
                qn = str(q)
                res["queues"][qn]={}
                res["queues"][qn]["name"]=qn
                res["queues"][qn]['len'] = yield self.settings.oper.queue_len(q)
                st = yield self.settings.oper.queue_status(q) 
                res["queues"][qn]['status'] = st["status"] if st['status'] else ""
                pl = yield self.settings.oper.queue_policy_get(q)
                res["queues"][qn]['policy'] = pl if pl else ""

            res['redis'] = repr(self.settings.db)
            res['count'] = len(ql)
            if jsoncallback is not None: res = "%s(%s)" % (jsoncallback, res)
            self.finish(res)

        else:
            try:
                qlen = yield self.settings.oper.queue_len(queue)
            except Exception, e:
                log.msg("ERROR: oper.queue_len('%s') failed: %s" % (queue, e))
                raise cyclone.web.HTTPError(503)

            resp = "%s" % cyclone.escape.json_encode({
                "redis": repr(self.settings.db),
                "queue": queue, "len": qlen})
            
            if jsoncallback is not None: resp = "%s(%s)" % (jsoncallback, resp)
            self.finish(resp)


class CometDispatcher(object):
    def __init__(self, oper, del_obj=True):
        self.oper = oper
        self.queue = defer.DeferredQueue()
        self.presence = defaultdict(lambda: [])
        self.qcounter = defaultdict(lambda: 0)
        self.queue.get().addCallback(self._new_data)
        #task.LoopingCall(self._auto_dispatch).start(1) # secs between checkings
        task.LoopingCall(self._notify_on_new_messages).start(1) # backoff t 
        task.LoopingCall(self._counters_cleanup).start(30) # presence maintenance
        self.delete_objects = del_obj

    def _new_data(self, queue_name):
        self.dispatch(queue_name)
        self.queue.get().addCallback(self._new_data)

    def _auto_dispatch(self):
        for queue_name, handlers in self.presence.items():
            self.dispatch(queue_name, handlers)
    
    @defer.inlineCallbacks
    def _notify_on_new_messages(self):
        try:
            ql = [q for q in self.presence.keys() if len(self.presence[q]) > 0]
            if len(ql) > 0:
                print "ql: %s" % ql
                qstat = yield self.oper.multi_queue_by_status(ql)
                ql = [q for q in ql if q not in qstat]

                def __micro_send(queue, policy, value):
                    print "presence for %s: %s" % (queue, value)
                    if value is not None and queue is not None: 
                        self._dump(self.presence[queue], [value], [policy])

                # deferred
                self.oper.queue_block_multi_get(ql).addCallback(__micro_send)
            else:
                print "skipping - no presence"
        except Exception, e:
            print "Exception: ", e

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
            try:
                policy, contents = yield self.oper.queue_tail(queue_name, delete_obj = self.delete_objects)
                assert policy and contents and isinstance(contents, types.ListType)
            except:
                defer.returnValue(None)
             
            self._dump(handlers, contents, policy)

    def _dump(self, handlers, contents, policy = None):
        if policy is None:
            policy == core.POLICY_BROADCAST
        size = len(handlers)
        if policy == core.POLICY_BROADCAST:
            self._send(handlers, contents)

        elif policy == core.POLICY_ROUNDROBIN:
            idx = self.qcounter[queue_name] % size
            self._send((handlers[idx],), contents)
            self.qcounter[queue_name] += 1

    def _send(self, handlers, contents): 
        for handler in handlers:
            for content in contents:
                try:
                    handler.write(cyclone.escape.json_encode(content))
                    handler.flush()
                except Exception, e:
                    log.msg("ERROR: Cannot write to comet client: %s = %s" % (handler, e))


class QueueControlHandler(cyclone.web.RequestHandler):
    """ QueueControlHandler stops/starts a queue (pause consumers)"""

    @authorize("rest_consumer")
    @defer.inlineCallbacks
    def get(self, queue):
        self.set_header("Content-Type", "application/json")

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

    @authorize("rest_producer")
    @defer.inlineCallbacks
    def post(self, queue):
        status = self.get_argument("status", None)
        jsoncallback = self.get_argument("callback", None)

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

        resp = "%s" % cyclone.escape.json_encode({"stat": qstat })

        if jsoncallback is not None: resp = "%s(%s)" % (jsoncallback, resp)
        self.finish("%s\r\n" % resp)


class WebSocketQueueHandler(cyclone.websocket.WebSocketHandler):
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

    def headersReceived(self):
        # for authenticated websocket clientes, the browser must set a
        # cookie like this:
        #   document.cookie = "auth=user:password"
        #
        # see ACL.check_password for details
        try:
            self.settings.acl.apply(self, "websocket_consumer", websocket=True)
        except:
            raise cyclone.web.HTTPError(401)

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


class ACL(object):
    def __init__(self, filename):
        self.md5 = None
        self.filename = filename

        self.rest_producer = {}
        self.rest_consumer = {}
        self.comet_consumer = {}
        self.websocket_consumer = {}

        self.parse(True)

    def parse(self, firstRun=False):
        try:
            if(self.filename.startswith('/') or os.path.exists(self.filename)):
                fp = open(self.filename)
            else:
                import pkg_resources as pkg
                fp = pkg.resource_stream('restmq.assets', self.filename)
            
            md5 = hashlib.md5(fp.read()).hexdigest()

            if self.md5 is None:
                self.md5 = md5
            else:
                if self.md5 == md5:
                    return fp.close()

            fp.seek(0)
            cfg = ConfigParser()
            cfg.readfp(fp)
            fp.close()

        except Exception, e:
            if firstRun:
                raise e
            else:
                log.msg("ERROR: Could not reload configuration: %s" % e)
                return
        else:
            if not firstRun:
                log.msg("Reloading ACL configuration")

        for section in ("rest:producer", "rest:consumer", "comet:consumer", "websocket:consumer"):
            d = getattr(self, section.replace(":", "_"))

            try:
                hosts_allow = cfg.get(section, "hosts_allow")
                d["hosts_allow"] = hosts_allow != "all" and hosts_allow.split() or None
            except:
                d["hosts_allow"] = None

            try:
                hosts_deny = cfg.get(section, "hosts_deny")
                d["hosts_deny"] = hosts_deny != "all" and hosts_deny.split() or None
            except:
                d["hosts_deny"] = None

            try:
                username = cfg.get(section, "username")
                d["username"] = username
            except:
                d["username"] = None

            try:
                password = cfg.get(section, "password")
                d["password"] = password
            except:
                d["password"] = None

        reactor.callLater(60, self.parse)

    def check_password(self, client, username, password, websocket):
        try:
            if websocket is True:
                rusername, rpassword = client.get_cookie("auth").split(":", 1)
                assert username == rusername and password == rpassword

            else:
                authtype, authdata = client.request.headers["Authorization"].split()
                assert authtype == "Basic"
                rusername, rpassword = base64.b64decode(authdata).split(":", 1)
                assert username == rusername and password == rpassword
        except:
            raise InvalidPassword

    def apply(self, client, category, websocket=False):
        acl = getattr(self, category)
        require_password = acl["username"] and acl["password"]

        if acl["hosts_allow"]:
            for ip in acl["hosts_allow"]:
                if client.request.remote_ip.startswith(ip):
                    if require_password:
                        self.check_password(client,
                            acl["username"], acl["password"], websocket)
                        return
                    else:
                        return

            if acl["hosts_deny"] is None:
                raise InvalidAddress("ip address %s not allowed" % client.request.remote_ip)

        if acl["hosts_deny"]:
            for ip in acl["hosts_deny"]:
                if client.request.remote_ip.startswith(ip):
                    raise InvalidAddress("ip address %s not allowed" % client.request.remote_ip)

        if require_password:
            self.check_password(client, acl["username"], acl["password"], websocket)


class Application(cyclone.web.Application):
    def __init__(self, acl_file, redis_host, redis_port, redis_pool, redis_db):
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

        try:
            acl = ACL(acl_file)
        except Exception, e:
            log.msg("ERROR: Cannot load ACL file: %s" % e)
            raise RuntimeError("Cannot load ACL file: %s" % e)

        db = cyclone.redis.lazyConnectionPool(
            redis_host, redis_port,
            poolsize=redis_pool, dbid=redis_db)

        oper = core.RedisOperations(db)

        settings = {
            "db": db,
            "acl": acl,
            "oper": oper,
            "comet": CometDispatcher(oper),
            "static_path": pkg.resource_filename('restmq', 'static'),
            "template_path": pkg.resource_filename('restmq', 'templates'),
        }

        cyclone.web.Application.__init__(self, handlers, **settings)

