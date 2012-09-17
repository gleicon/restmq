#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
import cyclone.redis
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
        rd = yield cyclone.redis.RedisConnectionPool()
    except Exception, e:
        print "Error creating redis pool %s" % e
        defer.returnValue(None)

    ro = core.RedisOperations(rd)

    if opt.producer == True:
        print "Running as producer"
        uuid = yield ro.queue_add(QUEUENAME, json.dumps({'value':'a value'}))
        print 'uuid: %s' % uuid

    if opt.consumer == True:
    	print "Running as consumer"
        (policy, ret) = yield ro.queue_get( QUEUENAME)
        if ret != None:
            print "value: %s" % ret['value'] #json.loads(ret['value'])
            print "policy: %s" % policy
        else:
            print 'empty queue'

    if opt.stats == True:
        ll = yield ro.queue_stats(QUEUENAME)
        print "list len: %s" % ll
  
        sm = yield ro.queue_all()
        print "all queues: %s" % sm

    if opt.non_consumer == True:
    	print "Running as consumer"
        (policy, ret) = yield ro.queue_get( QUEUENAME, softget=True)
        if ret != None:
            print "value: %s" % ret['value'] #json.loads(ret['value'])
            print "policy: %s" % policy
        else:
            print 'empty queue'

    if opt.get_policy == True:
    	print "GET queue policy"
        ret = yield ro.queue_policy_get(QUEUENAME)
        print repr(ret)

        if ret != None:
            print "value: %s" % ret['value'] #json.loads(ret['value'])
        else:
            print 'empty queue policy'

    if opt.set_policy == True:
    	print "SET queue policy"
        resp = yield ro.queue_policy_set(QUEUENAME, "roundrobin")
        print 'resp: %s' % resp

    if opt.get_del == True:
    	print "Running as getdel consumer"
        (policy, ret) = yield ro.queue_getdel(QUEUENAME)
        if ret != None and ret != False:
            print "value: %s" % ret['value'] #json.loads(ret['value'])
            print "policy: %s" % policy
        else:
            print 'empty queue'

    if opt.tail_mget == True:
    	print "Running as tail multiget"
        (policy, ret) = yield ro.queue_tail(QUEUENAME)
        if ret != None and ret != False:
            print "value: %s" % repr(ret) #json.loads(ret['value'])
            print "policy: %s" % policy
        else:
            print 'empty queue'

    if opt.count_objects == True:
    	print "Running as count object"
        ret = yield ro.queue_count_elements(QUEUENAME)
        if ret != None and ret != False:
            print "value: %s" % repr(ret) #json.loads(ret['value'])
        else:
            print 'empty queue'

    if opt.queue_last_items == True:
    	print "Running as count object"
        ret = yield ro.queue_last_items(QUEUENAME)
        if ret != None and ret != False:
            print "value: %s" % repr(ret) #json.loads(ret['value'])
        else:
            print 'empty queue'

    if opt.authorize == True:
    	print "Running authorization"
        ret = yield ro.authorize(QUEUENAME, 'aaa123')
        print ret
    
    if opt.create_auth == True:
    	print "Creating auth record"
        ret = yield ro._create_auth_record('aaa123', [QUEUENAME], ['create'])
        print ret


def main():
    p = OptionParser()
    p.add_option("-p", "--producer", action="store_true", dest="producer", help="Run as producer")
    p.add_option("-c", "--consumer", action="store_true", dest="consumer", help="Run as consumer")
    p.add_option("-g", "--non-consumer", action="store_true", dest="non_consumer", help="Run as a non destructive consumer")
    p.add_option("-s", "--stats", action="store_true", dest="stats", help="Stats")
    p.add_option("-q", "--get_policy", action="store_true", dest="get_policy", help="Get queue policy")
    p.add_option("-j", "--set_policy", action="store_true", dest="set_policy", help="Set queue policy")
    p.add_option("-k", "--get_delete", action="store_true", dest="get_del", help="Consumer get del")
    p.add_option("-t", "--tail_multiget", action="store_true", dest="tail_mget", help="Multi get 10 keys")
    p.add_option("-u", "--count_objects", action="store_true", dest="count_objects", help="Count objects of a given queue")
    p.add_option("-i", "--list_last_items", action="store_true", dest="queue_last_items", help="List the latest queue items")
    # authorization tests
    p.add_option("-a", "--authorize", action="store_true", dest="authorize", help="authorize a key for queues/privileges")
    p.add_option("-r", "--create_auth", action="store_true", dest="create_auth", help="Create an authorization record")


    (opt, args)=p.parse_args(sys.argv[1:])

    test_operations(opt, args).addCallback(lambda ign: reactor.stop())


if __name__ == "__main__":
	main()
	reactor.run()
