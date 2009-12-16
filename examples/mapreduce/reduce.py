#!/usr/bin/env python
# coding: utf-8

import sys
import simplejson
from twisted.web import client
from twisted.python import log
from twisted.internet import reactor

QUEUENAME = 'reducer'


class CometClient(object):
    def __init__(self):
        self.count=0

    def write(self, content):
        try:
            data = simplejson.loads(content)
        except Exception, e:
            log.err("cannot decode json: %s" % str(e))
            log.err("json is: %s" % content)
        else:
            val=simplejson.loads(data['value'])
            log.msg("file: %s count: %s" % (val['filename'], val['count']))
            self.count=self.count+val['count']
            log.msg("Total: %d" % self.count)

    def close(self):
        pass

if __name__ == "__main__":
    log.startLogging(sys.stdout)
    client.downloadPage("http://localhost:8888/c/%s" % QUEUENAME, CometClient())
    reactor.run()
