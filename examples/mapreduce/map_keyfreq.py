#!/user/bin/python
#
# map for restmq map/reduce example
# it counts a file's word and post to a queue called reducer
# output: {'filename':sys.argv[1], 'count': No of words}
#

import sys, json
import urllib, urllib2

QUEUENAME = 'reducer'

def wordfreq(file):
    try:
        f = open(file, 'r')
        words = f.read()
        f.close()
    except Exception, e:
        print "Exception: %s" % e
        return None
   
    wf={}
    wlist = words.split()
    for b in wlist:
        a=b.lower()
        if wf.has_key(a):
            wf[a]=wf[a]+1
        else:
           wf[a]=1
    return len(wf), wf

def enqueue(filename, count, wf):
    try:
        msg={"filename": filename, "count":count, "wordfreqlist":wf}
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
    l, wfl = wordfreq(sys.argv[1])
    print enqueue(sys.argv[1], l, wfl)
    print "count: %d" % l     
