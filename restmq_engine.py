#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import txredisapi
import simplejson
from restmq import core
from optparse import OptionParser
from twisted.internet import defer, reactor
        
QUEUENAME = 'test'

@defer.inlineCallbacks
def test_operations(opt, args):
    """ 
        test and docs for a redis based queue engine in python
        based on tx-redis
    """
    try:
        rd = yield txredisapi.RedisConnectionPool()
    except Exception, e:
        print "Error creating redis pool %s" % e
        defer.returnValue(None)

    ro = core.RedisOperations(rd)

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

    if opt.get_policy == True:
    	print "GET queue policy"
        ret = yield ro.queue_policy_get(QUEUENAME)
        print repr(ret)

        if ret != None:
            print "value: %s" % ret['value'] #simplejson.loads(ret['value'])
        else:
            print 'empty queue policy'

    if opt.set_policy == True:
    	print "SET queue policy"
        resp = yield ro.queue_policy_set(QUEUENAME, simplejson.dumps({'broadcast':True, 'enforce_take':False}))
        print 'resp: %s' % resp



def main():
    p = OptionParser()
    p.add_option("-p", "--producer", action="store_true", dest="producer", help="Run as producer")
    p.add_option("-c", "--consumer", action="store_true", dest="consumer", help="Run as consumer")
    p.add_option("-g", "--non-consumer", action="store_true", dest="non_consumer", help="Run as a non destructive consumer")
    p.add_option("-s", "--stats", action="store_true", dest="stats", help="Stats")
    p.add_option("-q", "--get_policy", action="store_true", dest="get_policy", help="Get queue policy")
    p.add_option("-j", "--set_policy", action="store_true", dest="set_policy", help="Set queue policy")

    (opt, args)=p.parse_args(sys.argv[1:])

    test_operations(opt, args).addCallback(lambda ign: reactor.stop())


if __name__ == "__main__":
	main()
	reactor.run()
