# coding: utf-8

import types
import simplejson
from twisted.internet import defer

POLICY_BROADCAST = 1
POLICY_ROUNDROBIN = 2
QUEUE_STATUS = 'queuestat:'
QUEUE_POLICY = "%s:queuepolicy"
QUEUE_NAME = '%s:queue' 

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
        - tricky part. there must be a queue_get() before. The object is out of the queue already. delete it.
        
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
        self.inverted_policies = dict([[v, k] for k, v in self.policies.items()])
        self.QUEUESET = 'QUEUESET' # the set which holds all queues
        self.PUBSUB_SUFIX = 'PUBSUB'

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

    @defer.inlineCallbacks
    def authorize(self, queue, authkey):
        """ Authorize an operation for a given queue using an authentication key
            The basic mechanism is a check against Redis to see if key named AUTHKEY:<authkey value> exists
            If it exists, check against its content to see wheter the queue is authorized. 
            Authorization is either read/write a queue and create new queues
            queues and priv are lists in the authorization record
            returns boolean 
        """
        queue, authkey = self.normalize(queue), self.normalize(authkey)
        # get key and analyze {'queues': ['q1','q2','q3'], 'privs': ['create']}
        avkey = "AUTHKEY:%s" % authkey
        authval = yield self.redis.get(avkey.encode('utf-8'))
        if authval == None:
            defer.returnValue(False)
        try:
            adata = simplejson.loads(authval)
        except Exception, e:
            defer.returnValue(None)
        if queue in adata['queues']:
            defer.returnValue(True)
        elif 'create' in adata['privs']:
            defer.returnValue(True)

        defer.returnValue(False)

    @defer.inlineCallbacks
    def _create_auth_record(self, authkey, queues=[], privs=[]):
        """ create a authorization record. queues and privs are lists """
        authkey = self.normalize(authkey)
        avkey = "AUTHKEY:%s" % authkey
        avkey = self.normalize(avkey)
        authrecord = {'queues': queues, 'privs':privs}

        res = yield self.redis.set(avkey, simplejson.dumps(authrecord))
        defer.returnValue(res)

    @defer.inlineCallbacks
    def queue_add(self, queue, value, ttl=None):
        queue, value = self.normalize(queue), self.normalize(value)

        uuid = yield self.redis.incr("%s:UUID" % queue)
        key = '%s:%d' % (queue, uuid)
        res = yield self.redis.set(key, value)
        if ttl is not None:
            res = yield self.redis.expire(key, ttl)
        internal_queue_name = QUEUE_NAME % self.normalize(queue)
        if uuid == 1: # TODO: use ismember()
            # either by checking uuid or by ismember, this is where you must know if the queue is a new one.
            # add to queues set
            res = yield self.redis.sadd(self.QUEUESET, queue)

            ckey = '%s:%s' % (QUEUE_STATUS, queue)
            res = yield self.redis.set(ckey, self.STARTQUEUE)

        res = yield self.redis.lpush(internal_queue_name, key)
        defer.returnValue(key)

    @defer.inlineCallbacks
    def queue_get(self, queue, softget=False): 
        """
            GET can be either soft or hard. 
            SOFTGET means that the object is not POP'ed from its queue list. It only gets a refcounter which is incremente for each GET
            HARDGET is the default behaviour. It POPs the key from its queue list.
            NoSQL dbs as mongodb would have other ways to deal with it. May be an interesting port.
            The reasoning behing refcounters is that they are important in some job scheduler patterns.
            To really cleanup the queue, one would have to issue a DEL after a hard GET.
        """
        policy = None
        queue = self.normalize(queue)
        lkey = QUEUE_NAME % self.normalize(queue)
        if softget == False:
            okey = yield self.redis.rpop(lkey)
        else:
            okey = yield self.redis.lindex(lkey, "-1")

        if okey == None:
            defer.returnValue((None, None))

        qpkey = QUEUE_POLICY % queue
        (policy, val) = yield self.redis.mget([qpkey, okey.encode('utf-8')])
        c=0
        if softget == True:
            c = yield self.redis.incr('%s:refcount' % okey.encode('utf-8'))

        defer.returnValue((policy or POLICY_BROADCAST, {'key':okey, 'value':val, 'count':c}))
    
    @defer.inlineCallbacks
    def queue_del(self, queue, okey):
        """
            DELetes an element from redis (not from the queue).
            Its important to make sure a GET was issued before a DEL. Its a kinda hard to guess the direct object key w/o a GET tho.
            the return value contains the key and value, which is a del return code from Redis. > 1 success and N keys where deleted, 0 == failure
        """
        queue, okey = self.normalize(queue), self.normalize(okey)
        val = yield self.redis.delete(okey)
        defer.returnValue({'key':okey, 'value':val})

    @defer.inlineCallbacks
    def queue_len(self, queue):
        lkey = QUEUE_NAME % self.normalize(queue)
        ll = yield self.redis.llen(lkey)
        defer.returnValue(ll)

    @defer.inlineCallbacks
    def queue_all(self):
        sm = yield self.redis.smembers(self.QUEUESET)
        defer.returnValue({'queues': sm})

    @defer.inlineCallbacks
    def queue_getdel(self, queue):
        policy = None
        queue = self.normalize(queue)
        lkey = QUEUE_NAME % self.normalize(queue)

        okey = yield self.redis.rpop(lkey) # take from queue's list
        if okey == None:
            defer.returnValue((None, False))

        okey = self.normalize(okey)
        nkey = '%s:lock' % okey
        ren = yield self.redis.rename(okey, nkey) # rename key

        if ren == None:
            defer.returnValue((None,None))

        qpkey = QUEUE_POLICY % queue
        (policy, val) = yield self.redis.mget(qpkey, nkey)
        delk = yield self.redis.delete(nkey)
        if delk == 0:
            defer.returnValue((None, None))
        else:
            defer.returnValue((policy, {'key':okey, 'value':val}))

    @defer.inlineCallbacks
    def queue_policy_set(self, queue, policy):
        queue, policy = self.normalize(queue), self.normalize(policy)
        if policy in ("broadcast", "roundrobin"):
            policy_id = self.policies[policy]
            qpkey = QUEUE_POLICY % queue
            res = yield self.redis.set(qpkey, policy_id)
            defer.returnValue({'queue': queue, 'response': res})
        else:
            defer.returnValue({'queue': queue, 'response': ValueError("invalid policy: %s" % repr(policy))})

    @defer.inlineCallbacks
    def queue_policy_get(self, queue):
        queue = self.normalize(queue)
        qpkey = QUEUE_POLICY % queue
        val = yield self.redis.get(qpkey)
        defer.returnValue({'queue':queue, 'value': self.inverted_policies.get(val, "unknown")})

    @defer.inlineCallbacks
    def queue_tail(self, queue, keyno=10, delete_obj=False): 
        """
            TAIL follows on GET, but returns keyno keys instead of only one key.
            keyno could be a LLEN function over the queue list, but it lends almost the same effect.
            LRANGE could too fetch the latest keys, even if there was less than keyno keys. MGET could be used too.
            TODO: does DELete belongs here ?
            returns a tuple (policy, returnvalues[])
        """
        policy = None
        queue = self.normalize(queue)
        lkey = QUEUE_NAME % self.normalize(queue)
        multivalue = []
        for a in range(keyno):
            nk = yield self.redis.rpop(lkey)
            if nk != None:
                t = nk.encode('utf-8')
            else:
                continue

            if delete_obj == True:
                okey = self.normalize(t)
                t = '%s:lock' % okey
                ren = yield self.redis.rename(okey, t)
                if ren == None: continue

                v = yield self.redis.get(t)
                delk = yield self.redis.delete(t)
                if delk == 0: continue
            else:
                v = yield self.redis.get(t)

            multivalue.append({'key': okey, 'value':v.encode('utf-8')})

        qpkey = QUEUE_POLICY % queue
        policy = yield self.redis.get(qpkey)
        defer.returnValue((policy or POLICY_BROADCAST, multivalue))

    @defer.inlineCallbacks
    def queue_count_elements(self, queue):
        # this is necessary to evaluate how many objects still undeleted on redis.
        # seems like it triggers a condition which the client disconnects from redis
        try:
            lkey = '%s*' % self.normalize(queue)
            ll = yield self.redis.keys(lkey)
            defer.returnValue({"objects":len(ll)})
        except Exception, e:
            defer.returnValue({"error":str(e)})

    @defer.inlineCallbacks
    def queue_last_items(self, queue, count=10):
        """
            returns a list with the last count items in the queue
        """
        queue = self.normalize(queue)
        lkey = QUEUE_NAME % self.normalize(queue)
        multivalue = yield self.redis.lrange(lkey, 0, count-1)

        defer.returnValue( multivalue)

    @defer.inlineCallbacks
    def queue_changestatus(self, queue, status):
        """Statuses: core.STOPQUEUE/core.STARTQUEUE"""
        if status != self.STOPQUEUE and status != self.STARTQUEUE:
            defer.returnValue(None)

        key = '%s:%s' % (QUEUE_STATUS, queue)
        res = yield self.redis.set(key, status)
        defer.returnValue({'queue':queue, 'status':status})

    @defer.inlineCallbacks
    def queue_status(self, queue):
        key = '%s:%s' % (QUEUE_STATUS, queue)
        res = yield self.redis.get(key)
        defer.returnValue({'queue':queue, 'status':res})

    @defer.inlineCallbacks
    def queue_purge(self, queue):
        #TODO Must del all keys (or set expire)
        #it could rename the queue list, add to a deletion SET and use a task to clean it

        lkey = QUEUE_NAME % self.normalize(queue)
        res = yield self.redis.delete(lkey)
        defer.returnValue({'queue':queue, 'status':res})

    @defer.inlineCallbacks
    def pubsub(self, queue_name, content):
        key = "%s:%s" % (queue_name, self.PUBSUB_SUFIX)
        r = yield self.redis.publish(key, content)
