#!/user/bin/python
#
# functional test for medium/big messages
# queue, check size both on restmq and redis
# make sure the queue is empty

import sys, json
import urllib, urllib2
import difflib
import redis
import hashlib
import time

QUEUENAME = 'bigmessages_%s' % time.time()

def str_checksum(str_m):
    return hashlib.md5(str_m).hexdigest()

def read_msg(file):
    try:
        f = open(file, 'r')
        words = f.read()
        f.close()
    except Exception, e:
        print "Exception: %s" % e
    return words

def enqueue(filename, content):
    try:
        msg={'filename': filename, 'len':len(content), 'content':content}
        data = urllib.urlencode({'queue':QUEUENAME, 'value':json.dumps(msg)})
        r = urllib2.Request('http://localhost:8888/', data)
        f = urllib2.urlopen(r)
        data = f.read()
        f.close()
    except urllib2.URLError, e:
        print e
    data = data.rstrip()
    ck_c = str_checksum(content)
    l_c = len(content)
    print '[Queued message] Key name: %s' % data
    print "[Queued message] checksum: %s size: %d bytes" % (ck_c, l_c)
    return (l_c, ck_c, data)

def dequeue():
    try:
        r = urllib2.Request('http://localhost:8888/q/%s' % QUEUENAME)
        f = urllib2.urlopen(r)
        data = f.read()
        f.close()
    except urllib2.URLError, e:
        print e
    data_dic = json.loads(data)
    dd2 = json.loads(data_dic['value'])
    content = dd2['content']
    ck_c = str_checksum(content)
    l_c = len(content)
    print "[Dequeued message] checksum: %s size: %d bytes" %(ck_c, l_c)
    return (l_c, ck_c, content)

def check_redis(redis_key):
    r = redis.Redis(host='localhost', port=6379, db=0)
    meh = r.get(redis_key)
    data_dic = json.loads(meh)
    content = data_dic['content']
    ck_c = str_checksum(content)
    l_c = len(content)
    print '[Redis] checksum: %s size for key %s: %d' % (ck_c, redis_key, l_c)
    return (l_c, ck_c)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "big message testing"
        print "Usage: bigmessage.py <file_to_count.txt>"
        sys.exit(-1)
    fname = sys.argv[1]
    content = read_msg(fname)
    (len_queued, ck_queued, redis_key) = enqueue(fname, content)
    (len_dequeued, ck_dequeued, ddq) = dequeue()
    (len_redis, ck_redis) = check_redis(redis_key)
    if (len_queued != len_dequeued): print 'Invalid dequeued message size'
    if (len_queued != len_redis): print 'Invalid redis message size'

#    d = difflib.Differ()
#    diff = d.compare(content.split(','), ddq.split(','))
#    print '\n'.join(list(diff))

