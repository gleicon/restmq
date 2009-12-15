# -*- coding: utf-8 -*-

from twisted.internet import reactor
from twisted.internet import protocol
from twisted.internet import defer

import txredis
import simplejson

# Hostname and Port number of a redis server
HOST = 'localhost'
PORT = 6379
#QUEUENAME = 'TESTQR'
QUEUENAME = 'test'


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
        a=0
        while a < 3:
            try:
                uuid = yield self.redis.incr("%s:UUID" % queue)
                key = '%s:%d' % (queue, uuid)
                res = yield self.redis.set(key, value)
                
                lkey = '%s:queue' % queue
                
                if uuid == 1: # TODO: use ismember()
                    # add to queues set
                    res = yield self.redis.sadd(self.QUEUESET, lkey)
                    print "set add: %s" % res
                break
            except: #TODO: rethink if retrying is really necessary. Spread around if it is.
                print "retry"
                a=a+1
                defer.returnValue(None)

        res = yield self.redis.push(lkey, key)
        defer.returnValue(key)

    @defer.inlineCallbacks
    def queue_get(self, queue, softget=False): 
        # TODO: how to implement get reference counting ? is it necessary (redis opers are atomic...) 
        # GETSET can help. MongoDB could do it if each queue object was a document. 
        # It could be another kind of GET, which doesn't pops from the queue list' LINDEX can help too (LINDEX 0 is 'pop w/o removing')
        # for now, non-destructive GET and refcounter are tied, and works by using the QUEUENAME:queue list as reference, and another key
        # as the refcount for those keys which are subject to softget.
        # refcounters are important in some job scheduler patterns.
        # TODO: cleanup in delete

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
        val = yield self.redis.delete(okey.encode('utf-8'))
        defer.returnValue({'key':okey, 'value':val}) # del return 1 if one or more keys where delete, 0 if no key where found

    @defer.inlineCallbacks
    def queue_stats(self, queue):
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
def test_operations(opt, args):
    """ 
        test and docs for a redis based queue engine in python
        based on tx-redis
    """
    try:
        rd = yield txredis.RedisConnectionPool()
    except Exception, e:
        print "Error creating redis pool %s" % e
        defer.returnValue(None)

    ro = RedisOperations(rd)

    if opt.producer == True:
        print "Running as producer"
        uuid = yield ro.queue_add(QUEUENAME, simplejson.dumps({'value':'a value'}))
        print 'uuid: %s' % uuid

    if opt.consumer == True:
    	print "Running as consumer"
        ret = yield ro.queue_get( QUEUENAME)
        print repr(ret)

        if ret != None:
            print "value: %s" % ret['value'] #simplejson.loads(ret['value'])
        else:
            print 'empty queue'

    if opt.stats == True:
        ll = yield ro.queue_stats(QUEUENAME)
        print "list len: %s" % ll
  
        sm = yield ro.queue_all()
        print "all queues: %s" % sm

    if opt.non_consumer == True:
    	print "Running as consumer"
        ret = yield ro.queue_get(QUEUENAME, softget=True)
        print repr(ret)

        if ret != None:
            print "value: %s" % ret['value'] #simplejson.loads(ret['value'])
        else:
            print 'empty queue'

        
def main():
    from optparse import OptionParser
    import sys

    p = OptionParser()
    p.add_option("-p", "--producer", action="store_true", dest="producer", help="Run as producer")
    p.add_option("-c", "--consumer", action="store_true", dest="consumer", help="Run as consumer")
    p.add_option("-g", "--non-consumer", action="store_true", dest="non_consumer", help="Run as a non destructive consumer")
    p.add_option("-s", "--stats", action="store_true", dest="stats", help="Stats")

    (opt, args)=p.parse_args(sys.argv[1:])

    test_operations(opt, args).addCallback(lambda ign: reactor.stop())


if __name__ == "__main__":
	main()
	reactor.run()


