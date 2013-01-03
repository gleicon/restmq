# coding: utf-8
#
# Copyright 2009 Gleicon Moraes
# Powered by cyclone
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


import cyclone.web

from twisted.internet import defer
#from twisted.python import log

from restmq.storage import DatabaseMixin
from restmq.utils import BaseHandler
from restmq.utils import SmartHandler
#from restmq.utils import TemplateFields
from restmq.utils import authorize


class IndexHandler(BaseHandler, DatabaseMixin):
    @authorize("rest_consumer")
    @defer.inlineCallbacks
    def get(self):
        q = self.get_argument("queue", None)
        if q is None:
            self.redirect("/static/index.html")
            defer.returnValue(None)

        policy, value = yield self.MQ.queue_get(q)
        if value:
            SmartHandler(self).finish(value)
        else:
            raise cyclone.web.HTTPError(404)  # Not Found

    @authorize("rest_producer")
    @defer.inlineCallbacks
    def post(self):
        q = self.get_argument("queue")
        v = self.get_argument("msg", self.get_argument("value", None))
        ttl = self.get_argument("ttl", None)

        if v is None:
            raise cyclone.web.HTTPError(400)  # Bad Request

        result = yield self.MQ.queue_add(q, v, ttl=ttl)
        if result:
            #self.settings.comet.queue.put(q)
            SmartHandler(self).finish(result)
        else:
            raise cyclone.web.HTTPError(400)  # Bad Request


class RawQueueHandler(BaseHandler, DatabaseMixin):
    def get(self):
        self.render("help.html")

    @authorize("rest_producer")
    @defer.inlineCallbacks
    def post(self):
        v = self.get_argument("msg", self.get_argument("body", None))
        try:
            assert v is not None
            jsonbody = cyclone.escape.json_decode(v)
            assert jsonbody["cmd"]
            for k, v in jsonbody.items():
                jsonbody[k] = v.encode("utf-8")
        except:
            raise cyclone.web.HTTPError(400)  # Bad Request

        result = yield self.MQ.execute(jsonbody)
        if result:
            self.finish(result)
        else:
            self.finish({"error": "null resultset"})


class RestQueueHandler(BaseHandler, DatabaseMixin):
    """
    Applies HTTP Methods to a given queue.
    GET /q/queuename gets an object out of the queue.
    POST /q/queuename adds an object to the queue.
    DELETE purge and delete the queue. It disconnects all live consumers.
    (Live consumers are Comet API, WebSockets or SSE)
    """
    @authorize("rest_consumer")
    @defer.inlineCallbacks
    def get(self, q):
        if q:
            policy, value = yield self.MQ.queue_get(q)

            if value:
                SmartHandler(self).finish(value)
            else:
                raise cyclone.web.HTTPError(204)  # No Content
        else:
            allqueues = yield self.MQ.queue_all()
            self.render("list_queues.html", route="q", extended_route="REST",
                                            allqueues=allqueues["queues"])

    @authorize("rest_producer")
    @defer.inlineCallbacks
    def post(self, q):
        v = self.get_argument("msg", self.get_argument("value", None))
        ttl = self.get_argument("ttl", None)

        if v is None:
            raise cyclone.web.HTTPError(400)  # Bad Request

        result = yield self.MQ.queue_add(q, v, ttl=ttl)
        if result:
            #self.settings.comet.queue.put(q)
            SmartHandler(self).finish(result)
        else:
            raise cyclone.web.HTTPError(400)  # Bad Request

    @authorize("rest_producer")
    @defer.inlineCallbacks
    def delete(self, q):
#        clients = self.settings.comet.presence.get(q, [])
#        for handler in clients:
#            try:
#                handler.finish()
#            except Exception, e:
#                log.msg("ERROR: cannot close client connection: %s = %s" %
#                        (handler, e))

        result = yield self.MQ.queue_purge(q)
        SmartHandler(self).finish(result)


class PolicyQueueHandler(BaseHandler, DatabaseMixin):
    """
    Get and set queue policies: broadcast or roundrobin.
    """
    @authorize("rest_consumer")
    @defer.inlineCallbacks
    def get(self, q):
        policy, policy_name = yield self.MQ.queue_policy_get(q)
        SmartHandler(self).finish({"queue": q, "value": policy_name})

    @authorize("rest_producer")
    @defer.inlineCallbacks
    def post(self, q):
        result = yield self.MQ.queue_policy_set(q, self.get_argument("policy"))
        SmartHandler(self).finish(result)


class JobQueueInfoHandler(BaseHandler, DatabaseMixin):
    """
    A job scheduler.
    """
    @defer.inlineCallbacks
    def get(self, q):
        self.render("jobs.html",
                    queue=q,
                    jobs=(yield self.MQ.queue_last_items(q)),
                    job_count=(yield self.MQ.queue_len(q)),
                    queue_size=(yield self.MQ.queue_count_elements(q)))


class QueueControlHandler(BaseHandler, DatabaseMixin):
    """
    Get and set queue flow control: play, pause consumers.
    """
    @authorize("rest_consumer")
    @defer.inlineCallbacks
    def get(self, q):
        if q:
            qs = yield self.MQ.queue_status(q)
            stats = {"redis": str(self.MQ.redis), "queue": q, "status": qs}
        else:
            data = []
            queues = yield self.MQ.queue_all()
            for q in queues["queues"]:
                data.append((yield self.MQ.queue_status(q)))

            stats = {"redis": str(self.MQ.redis), "queues": data,
                     "count": len(data)}

        self.set_header("Content-Type", "application/json")
        self.finish("%s\r\n" % cyclone.escape.json_encode(stats))

    @authorize("rest_producer")
    @defer.inlineCallbacks
    def post(self, q):
        s = self.get_argument("status")
        if not q:
            q = self.get_argument("queue")

        if s == "start":
            r = yield self.QM.queue_changestatus(q, self.QM.STARTQUEUE)
        elif s == "stop":
            r = yield self.QM.queue_changestatus(q, self.QM.STOPQUEUE)
        else:
            r = "invalid status: %s" % s

        r = "%s" % cyclone.escape.json_encode({"stat": r})

        self.set_header("Content-Type", "application/json")
        c = self.get_argument("callback", None)
        if c:
            self.finish("%s(%s);\r\n" % (c, r))
        else:
            self.finish("%s\r\n" % r)


class StatusHandler(BaseHandler, DatabaseMixin):
    @authorize("rest_consumer")
    @defer.inlineCallbacks
    def get(self, q):
        if q:
            qlen = yield self.MQ.queue_len(q)
            stats = {"redis": str(self.MQ.redis), "queue": q, "len": qlen}
        else:
            data = {}
            stats = {}
            queues = yield self.MQ.queue_all()
            for q in queues["queues"]:
                data[q] = {
                    "len": (yield self.MQ.queue_len(q)),
                    "status": (yield self.MQ.queue_status(q)).get("status"),
                    "policy": (yield self.MQ.queue_policy_get(q))[1],
                }

            stats["queues"] = data
            stats["count"] = len(data)
            stats["redis"] = str(self.MQ.redis)

        self.set_header("Content-Type", "application/json")
        c = self.get_argument("callback", None)
        if c:
            self.finish("%s(%s);\r\n" % (c, stats))
        else:
            self.finish("%s\r\n" % stats)


class CometConsumerHandler(BaseHandler):
    pass


class WebSocketConsumerHandler(BaseHandler):
    pass


class SSEConsumerHandler(BaseHandler):
    pass
