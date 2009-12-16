# coding: utf-8

from twisted.internet import defer
import simplejson

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
        self.QUEUESET = 'QUEUESET' # the set which holds all queues
        self.redis = redis


    @defer.inlineCallbacks
    def queue_add(self, queue, value):

        uuid = yield self.redis.incr("%s:UUID" % queue)
        key = '%s:%d' % (queue, uuid)
        res = yield self.redis.set(key, value)
        
        lkey = '%s:queue' % queue
        
        if uuid == 1: # TODO: use ismember()
            # either by checking uuid or by ismember, this is where you must know if the queue is a new one.
            # add to queues set
            res = yield self.redis.sadd(self.QUEUESET, lkey)
            print "set add: %s" % res
            # add default queue policy, for now just enforce_take is set
            qpkey = "%s:queuepolicy" % (queue)
            defaultqp = {'enforce_take':False, 'broadcast':True}
            res = yield self.redis.set(qpkey, simplejson.dumps(defaultqp).encode('utf-8'))


        res = yield self.redis.push(lkey, key)
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

        lkey = '%s:queue' % queue
        if softget == False:
            okey = yield self.redis.pop(lkey)
        else:
            okey = yield self.redis.lindex(lkey, "0")

        if okey == None:
            defer.returnValue(None)
            return
        val = yield self.redis.get(okey.encode('utf-8'))
        c=0
        if softget == True:
            c = yield self.redis.incr('%s:refcount' % okey.encode('utf-8'))

        defer.returnValue({'key':okey, 'value':val, 'count':c})
    
    @defer.inlineCallbacks
    def queue_del(self, queue, okey):
        """
            DELetes an element from redis (not from the queue).
            Its important to make sure a GET was issued before a DEL. Its a kinda hard to guess the direct object key w/o a GET tho.
            the return value contains the key and value, which is a del return code from Redis. > 1 success and N keys where deleted, 0 == failure
        """
        val = yield self.redis.delete(okey.encode('utf-8'))
        defer.returnValue({'key':okey, 'value':val})

    @defer.inlineCallbacks
    def queue_stats(self, queue):
        #TODO: more stats 
        lkey = '%s:queue' % queue
        ll = yield self.redis.llen(lkey)
        defer.returnValue({'len': ll})

    @defer.inlineCallbacks
    def queue_all(self):
        sm = yield self.redis.smembers(self.QUEUESET)
        defer.returnValue({'queues': sm})
    
    @defer.inlineCallbacks
    def queue_getdel(self, queue):
        lkey = '%s:queue' % queue
        okey = yield self.redis.pop(lkey) # take from queue's list
        if okey == None:
            defer.returnValue(False)
            return
        nkey = '%s:lock' % okey.encode('utf-8')
        ren = yield self.redis.rename(okey.encode('utf-8'), nkey.encode('utf-8')) # rename key

        if ren == None:
            defer.returnValue(None)
            return

        val = yield self.redis.get(nkey.encode('utf-8'))
        delk = yield self.redis.delete(nkey.encode('utf-8'))
        if delk == 0:
            defer.returnValue(None)
        defer.returnValue({'key':okey, 'value':val})

    @defer.inlineCallbacks
    def queue_policy_set(self, queue, policy):
        qpkey = "%s:queuepolicy" % (queue)
        res = yield self.redis.set(qpkey.encode('utf-8'), policy.encode('utf-8'))
        defer.returnValue({'queue': queue, 'response': res})

    @defer.inlineCallbacks
    def queue_policy_get(self, queue):
        qpkey = "%s:queuepolicy" % (queue)
        val = yield self.redis.get(qpkey.encode('utf-8'))
        defer.returnValue({'queue':queue, 'value': val})

