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


def main():
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
