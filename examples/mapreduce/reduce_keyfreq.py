#!/usr/bin/env python
# coding: utf-8

import sys
import json
from twisted.web import client
from twisted.python import log
from twisted.internet import reactor

QUEUENAME = 'reducer'


class CometClient(object):
    def __init__(self):
        self.count=0
        self.wordfreq={}

    def write(self, content):
        try:
			content.rstrip('\n')
			c = content.split('\n')
			data=[]
			for line in c:
				if len(line) < 2: continue
				data.append(json.loads(line))
        except Exception, e:
            log.err("cannot decode json: %s" % str(e))
            log.err("json is: %s" % content)
        else:
            jobs=[]
            for v in data:
                    val=json.loads(v['value'])
                    jobs.append(v['key'])
                    log.msg("file: %s count: %s" % (val['filename'], val['count']))
                    self.count=self.count+val['count']
                    twf = val['wordfreqlist']
                    for a in twf.keys():
                        b=a.lower()
                        if self.wordfreq.has_key(b):
                            self.wordfreq[b]=self.wordfreq[b]+twf[b]
                        else:
                            self.wordfreq[b]=twf[b]
						 						
            log.msg("Total: %d" % self.count)
            log.msg("Word Frequence: ", str(self.wordfreq))
            print "---------------- Job %s -----------------" % jobs
    def close(self):
        pass

if __name__ == "__main__":
    log.startLogging(sys.stdout)
    client.downloadPage("http://localhost:8888/c/%s" % QUEUENAME, CometClient())
    reactor.run()
