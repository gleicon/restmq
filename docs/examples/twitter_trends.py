# simple twitter producer for restmq. point your browser to http://localhost:8888/c/twitter and 
# execute it with python twitter_trends.py 

import json
import pickle, re, os, urllib, urllib2


def get_url(url):
    try:
        f = urllib2.urlopen(url)
        data = f.read()
        f.close()
    except urllib2.URLError, e:
        print e.code
        print e.read()
    return data

def post_in_queue(subject, author, text):
    try:
        msg={'subject': subject, 'author':author, 'text':text}
        data = urllib.urlencode({'queue':'twitter', 'value':json.dumps(msg)})
        r = urllib2.Request('http://localhost:8888/', data)
        f = urllib2.urlopen(r)
        data = f.read()
        f.close()
    except urllib2.URLError, e:
        print e.code
        print e.read()
    print data

filename = "last_topic_ids.db"

if os.path.exists(filename):  
    last_topic_ids = pickle.load(file(filename, 'r+b'))  
else:  
    last_topic_ids = {}



trends_current = json.loads(get_url("http://search.twitter.com/trends/current.json"))
c = trends_current["trends"]

for a in c[c.keys()[0]]:
    if a['query'] not in last_topic_ids.keys():
        url = "http://search.twitter.com/search.json?q=%s" % (urllib.quote_plus(a['query']))
    else:
        url = "http://search.twitter.com/search.json?q=%s&since_id=%s" % (urllib.quote_plus(a['query']), last_topic_ids[a['query']])
    print "--------------------------------------"
    print "%s: %s" % (a['name'], url)
    statuses = json.loads(get_url(url))
    for s in statuses['results']:
        print repr(s)
        print "%s: %s" %(s['from_user'], s['text'])
        post_in_queue(a, s['from_user'], s['text'])    
    last_topic_ids[a['query']] = statuses['max_id']
    print "--------------------------------------"

print "Last topic and posts ids: %s" % last_topic_ids
pickle.dump(last_topic_ids, file(filename, 'w+b')) 

