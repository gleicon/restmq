#!/user/bin/python
#
# map for restmq map/reduce example
# it counts a file's word and post to a queue called reducer
# output: {'filename':sys.argv[1], 'count': No of words}
#

import sys, json
import urllib, urllib2

QUEUENAME = 'reducer'

def wc(file):
    try:
        f = open(file, 'r')
        words = f.read()
        f.close()
    except Exception, e:
        print "Exception: %s" % e

    return len(words.split())

def enqueue(filename, count):
    try:
        msg={'filename': filename, 'count':count}
        data = urllib.urlencode({'queue':QUEUENAME, 'value':json.dumps(msg)})
        r = urllib2.Request('http://localhost:8888/', data)
        f = urllib2.urlopen(r)
        data = f.read()
        f.close()
    except urllib2.URLError, e:
        print e

    return "Sent: %s: %d" %(filename, count)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "Usage: map.py <file_to_count.txt>"
        sys.exit(-1)
    count = wc(sys.argv[1])
    print enqueue(sys.argv[1], count)
