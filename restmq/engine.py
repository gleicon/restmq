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


import cyclone.escape
import cyclone.redis
import functools
import itertools
import types

from twisted.internet import defer
from twisted.python import log

POLICY_BROADCAST = 1
POLICY_ROUNDROBIN = 2
QUEUE_STATUS = "queuestat:"
QUEUE_POLICY = "%s:queuepolicy"
QUEUE_NAME = "%s:queue"


def safe(method):
    # This decorator functions makes all database calls safe from connection
    # errors. It returns an HTTP 503 (Service Unavailable) when redis is
    # temporarily disconnected.
    @defer.inlineCallbacks
    @functools.wraps(method)
    def run(self, *args, **kwargs):
        try:
            r = yield defer.maybeDeferred(method, self, *args, **kwargs)
        except cyclone.redis.ConnectionError, e:
            m = "redis.ConnectionError: %s" % e
            log.msg(m)
            raise cyclone.web.HTTPError(503, m)  # Service Unavailable
        else:
            defer.returnValue(r)

    return run


class RedisOperations:
    """
    add element to the queue:
        - increments a UUID record
        - store the object using a key as <queuename>:uuid
        - push this key into a list named <queuename>:queue
        - push this list name into the general QUEUESET
    get element from queue:
        - pop a key from the list
        - get and return, along with its key

    del element from the queue:
        - tricky part. there must be a queue_get() before. The object is out
          of the queue already. delete it.

    - TODO: the object may have an expiration instead of straight deletion
    - TODO: RPOPLPUSH can be used to put it in another queue as a backlog
    - TODO: persistence management (on/off/status)
    """

    def __init__(self, redis):
        self.STOPQUEUE = 0
        self.STARTQUEUE = 1
        self.redis = redis
        self.policies = {
            "broadcast": POLICY_BROADCAST,
            "roundrobin": POLICY_ROUNDROBIN,
        }
        self.inverted_policies = dict([[v, k]
                                        for k, v in self.policies.items()])
        self.QUEUESET = "QUEUESET"  # the set which holds all queues
        self.PUBSUB_SUFIX = "PUBSUB"

    def normalize(self, item):
        if isinstance(item, types.StringType):
            return item
        elif isinstance(item, types.UnicodeType):
            try:
                return item.encode("utf-8")
            except:
                raise ValueError("strings must be utf-8")
        else:
            raise ValueError("data must be utf-8")

    @safe
    @defer.inlineCallbacks
    def authorize(self, queue, authkey):
        """
        Authorize an operation for a given queue using an authentication key.

        The basic mechanism is a check against Redis to see if the key named
        AUTHKEY:<authkey value> exists.

        If it does, check against its content to see wheter the queue is
        authorized.

        Authorization is either read or write for a queue. Create new queues
        and priv are lists in the authorization record.

        Returns boolean.
        """
        queue, authkey = self.normalize(queue), self.normalize(authkey)
        # get key and analyze {"queues": ["q1","q2","q3"], "privs": ["create"]}
        avkey = "AUTHKEY:%s" % authkey
        authval = yield self.redis.get(avkey.encode("utf-8"))
        if authval is None:
            defer.returnValue(False)

        try:
            adata = cyclone.escape.json_decode(authval)
        except:
            defer.returnValue(None)

        if queue in adata["queues"]:
            defer.returnValue(True)
        elif "create" in adata["privs"]:
            defer.returnValue(True)

        defer.returnValue(False)

    @safe
    @defer.inlineCallbacks
    def _create_auth_record(self, authkey, queues=[], privs=[]):
        """ create a authorization record. queues and privs are lists """
        authkey = self.normalize(authkey)
        avkey = "AUTHKEY:%s" % authkey
        avkey = self.normalize(avkey)
        authrecord = {"queues": queues, "privs": privs}

        res = yield self.redis.set(avkey,
                                    cyclone.escape.json_encode(authrecord))
        defer.returnValue(res)

    @safe
    @defer.inlineCallbacks
    def queue_add(self, queue, value, ttl=None):
        queue, value = self.normalize(queue), self.normalize(value)
        uuid = yield self.redis.incr("%s:UUID" % queue)
        key = "%s:%d" % (queue, uuid)
        yield self.redis.set(key, value)

        if ttl is not None:
            yield self.redis.expire(key, ttl)

        internal_queue_name = QUEUE_NAME % self.normalize(queue)
        if uuid == 1:  # TODO: use ismember()
            # Either by checking uuid or by ismember, this is where you must
            # know if the queue is a new one.
            # Add to queues set.
            yield self.redis.sadd(self.QUEUESET, queue)
            ckey = "%s:%s" % (QUEUE_STATUS, queue)
            yield self.redis.set(ckey, self.STARTQUEUE)

        yield self.redis.lpush(internal_queue_name, key)
        defer.returnValue(key)

    @safe
    @defer.inlineCallbacks
    def queue_get(self, queue, softget=False):
        """
        GET can be either soft or hard.

        SOFTGET means that the object is not POP'ed from its queue list. It
        only gets a refcounter which is incremented for each GET.

        HARDGET is the default behaviour. It POPs the key from its queue list.

        NoSQL DBs such as MongoDB would have other ways to deal with it. May
        be an interesting port.

        The reason behing refcounters is that they are important in some job
        scheduler patterns. To really cleanup the queue, one would have to
        issue a DEL after a hard GET.
        """
        policy = None
        queue = self.normalize(queue)
        lkey = QUEUE_NAME % self.normalize(queue)
        if softget is False:
            okey = yield self.redis.rpop(lkey)
        else:
            okey = yield self.redis.lindex(lkey, "-1")

        if okey is None:
            defer.returnValue((None, None))

        qpkey = QUEUE_POLICY % queue
        (policy, val) = yield self.redis.mget([qpkey, okey.encode("utf-8")])
        c = 0
        if softget is True:
            c = yield self.redis.incr("%s:refcount" % okey.encode("utf-8"))

        defer.returnValue((policy or POLICY_BROADCAST,
                            {"key": okey, "value": val, "count": c}))

    @safe
    @defer.inlineCallbacks
    def queue_del(self, queue, okey):
        """
        DELetes an element from redis (not from the queue).

        It's important to make sure a GET was issued before a DEL. Its kinda
        hard to guess the direct object key without a GET tho.

        The return value contains the key and value, which is a del return
        code from Redis.

        Returns > 1 on success and the number of keys deleted, or 0 on failure.
        """
        queue, okey = self.normalize(queue), self.normalize(okey)
        val = yield self.redis.delete(okey)
        defer.returnValue({"key": okey, "value": val})

    @safe
    @defer.inlineCallbacks
    def queue_len(self, queue):
        lkey = QUEUE_NAME % self.normalize(queue)
        ll = yield self.redis.llen(lkey)
        defer.returnValue(ll)

    @safe
    @defer.inlineCallbacks
    def queue_all(self):
        sm = yield self.redis.smembers(self.QUEUESET)
        defer.returnValue({"queues": sm})

    @safe
    @defer.inlineCallbacks
    def queue_getdel(self, queue):
        policy = None
        queue = self.normalize(queue)
        lkey = QUEUE_NAME % self.normalize(queue)

        okey = yield self.redis.rpop(lkey)  # take from queue's list
        if okey is None:
            defer.returnValue((None, False))

        okey = self.normalize(okey)
        nkey = "%s:lock" % okey
        ren = yield self.redis.rename(okey, nkey)  # rename key

        if ren is None:
            defer.returnValue((None, None))

        qpkey = QUEUE_POLICY % queue
        (policy, val) = yield self.redis.mget(qpkey, nkey)
        delk = yield self.redis.delete(nkey)
        if delk == 0:
            defer.returnValue((None, None))
        else:
            defer.returnValue((policy, {"key": okey, "value": val}))

    @safe
    @defer.inlineCallbacks
    def queue_policy_set(self, queue, policy):
        queue, policy = self.normalize(queue), self.normalize(policy)
        if policy in ("broadcast", "roundrobin"):
            policy_id = self.policies[policy]
            qpkey = QUEUE_POLICY % queue
            res = yield self.redis.set(qpkey, policy_id)
            defer.returnValue(res)
            defer.returnValue({"queue": queue, "response": res})
        else:
            defer.returnValue(None)

    @safe
    @defer.inlineCallbacks
    def queue_policy_get(self, queue):
        queue = self.normalize(queue)
        qpkey = QUEUE_POLICY % queue
        val = yield self.redis.get(qpkey)
        name = self.inverted_policies.get(val, "broadcast")
        defer.returnValue([val, name])

    @safe
    @defer.inlineCallbacks
    def queue_tail(self, queue, keyno=10, delete_obj=False):
        """
        TAIL follows on GET, but returns keyno keys instead of only one key.

        keyno could be a LLEN function over the queue list, but it lends
        almost the same effect.

        LRANGE could too fetch the latest keys, even if there was less than
        keyno keys. MGET could be used too.

        TODO: does DELete belong here ?

        Returns a tuple (policy, returnvalues[])
        """
        policy = None
        queue = self.normalize(queue)
        lkey = QUEUE_NAME % self.normalize(queue)
        multivalue = []
        for a in range(keyno):
            nk = yield self.redis.rpop(lkey)
            if nk is not None:
                t = nk.encode("utf-8")
            else:
                continue

            if delete_obj is True:
                okey = self.normalize(t)
                t = "%s:lock" % okey
                ren = yield self.redis.rename(okey, t)
                if ren is None:
                    continue

                v = yield self.redis.get(t)
                delk = yield self.redis.delete(t)
                if delk == 0:
                    continue
            else:
                v = yield self.redis.get(t)

            multivalue.append({"key": okey, "value": v.encode("utf-8")})

        qpkey = QUEUE_POLICY % queue
        policy = yield self.redis.get(qpkey)
        defer.returnValue((policy or POLICY_BROADCAST, multivalue))

    @safe
    @defer.inlineCallbacks
    def queue_count_elements(self, queue):
        # This is necessary to evaluate how many objects are still
        # undeleted on redis.
        # Seems like it triggers a condition where clients disconnect
        # from redis.
        try:
            lkey = "%s*" % self.normalize(queue)
            ll = yield self.redis.keys(lkey)
            defer.returnValue({"objects": len(ll)})
        except Exception, e:
            defer.returnValue({"error": str(e)})

    @safe
    @defer.inlineCallbacks
    def queue_last_items(self, queue, count=10):
        """
            returns a list with the last count items in the queue
        """
        queue = self.normalize(queue)
        lkey = QUEUE_NAME % self.normalize(queue)
        multivalue = yield self.redis.lrange(lkey, 0, count - 1)

        defer.returnValue(multivalue)

    @safe
    @defer.inlineCallbacks
    def queue_changestatus(self, queue, status):
        """Statuses: core.STOPQUEUE/core.STARTQUEUE"""
        if status != self.STOPQUEUE and status != self.STARTQUEUE:
            defer.returnValue(None)

        key = "%s:%s" % (QUEUE_STATUS, queue)
        yield self.redis.set(key, status)
        defer.returnValue({"queue": queue, "status": status})

    @safe
    @defer.inlineCallbacks
    def queue_status(self, queue):
        key = "%s:%s" % (QUEUE_STATUS, queue)
        res = yield self.redis.get(key)
        defer.returnValue({"queue": queue, "status": res})

    @safe
    @defer.inlineCallbacks
    def queue_purge(self, queue):
        # TODO: Must del all keys (or set expire)
        # It could rename the queue list, add to a deletion SET and use a task
        # to clean it up.

        lkey = QUEUE_NAME % self.normalize(queue)
        res = yield self.redis.delete(lkey)
        defer.returnValue({"queue": queue, "status": res})

    @safe
    @defer.inlineCallbacks
    def pubsub(self, queue_name, content):
        key = "%s:%s" % (queue_name, self.PUBSUB_SUFIX)
        yield self.redis.publish(key, content)

    @safe
    @defer.inlineCallbacks
    def queue_block_multi_get(self, queue_list):
        """
        Waits on a list of queues, get back with the first queue that
        received data.

        This makes redis locallity very important as if there are other
        instances doing the same the policy won't be respected. OTOH it makes
        it fast by not polling lists and waiting x seconds.
        """
        ql = [QUEUE_NAME % self.normalize(queue) for queue in queue_list]
        res = yield self.redis.brpop(ql)
        if res is not None:
            q = self.normalize(res[1])
            qpkey = QUEUE_POLICY % q
            (p, v) = yield self.redis.mget([qpkey, q])
            defer.returnValue((q, p, {"key": q, "value": v}))
        else:
            defer.returnValue(None)

    @safe
    @defer.inlineCallbacks
    def multi_queue_by_status(self, queue_list, filter_by=None):
        if filter_by is None:
            filter_by = self.STARTQUEUE
        ql = ["%s:%s" % (QUEUE_STATUS, self.normalize(queue))
                        for queue in queue_list]
        res = yield self.redis.mget(ql)
        qs = [True if r != filter_by else False for r in res]
        r = itertools.compress(ql, qs)
        defer.returnValue(list(r))

    @defer.inlineCallbacks
    def cmd_add(self, jsonbody):
        if "queue" in jsonbody and "value" in jsonbody:
            k = yield self.queue_add(jsonbody["queue"], jsonbody["value"])
            defer.returnValue({
                "queue": jsonbody["queue"],
                "value": jsonbody["value"],
                "key": str(k),
            })
        else:
            defer.returnValue({"error": "missing arguments"})

    @defer.inlineCallbacks
    def cmd_get(self, jsonbody):
        if "queue" in jsonbody:
            p, e = yield self.queue_get(jsonbody["queue"], softget=True)
            if e is None:
                defer.returnValue({"error": "empty queue"})
            else:
                defer.returnValue({
                    "queue": jsonbody["queue"],
                    "value": e["value"],
                    "key": e["key"],
                    "count": e["count"],
                })
        else:
            defer.returnValue({"error": "missing arguments"})

    @defer.inlineCallbacks
    def cmd_take(self, jsonbody):
        if "queue" in jsonbody:
            p, e = yield self.queue_getdel(jsonbody["queue"])
            if e is False:
                defer.returnValue({"error": "empty queue"})
            elif e is None:
                defer.returnValue({"error": "getdel error"})

            defer.returnValue({
                "queue": jsonbody["queue"],
                "value": e["value"],
                "key": e["key"],
            })
        else:
            defer.returnValue({"error": "missing arguments"})

    @defer.inlineCallbacks
    def cmd_del(self, jsonbody):
        if "queue" in jsonbody and "key" in jsonbody:
            e = yield self.queue_del(jsonbody["queue"], jsonbody["key"])
            defer.returnValue({
                "queue": jsonbody["queue"],
                "deleted": True if e["value"] > 0 else False,
                "key": e["key"],
            })
        else:
            defer.returnValue({"error": "missing arguments"})

    def execute(self, jsonbody):
        m = getattr(self, "cmd_%s" % jsonbody["cmd"], None)
        if m:
            return m(jsonbody)
