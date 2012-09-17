#!/usr/bin/env python
# coding: utf-8

import sys
import json
from twisted.web import client
from twisted.python import log
from twisted.internet import reactor

class CometClient(object):
    def write(self, content):
        for json in content.splitlines():
            try:
                    data = json.loads(json)
                    data = data.get('value')
            except Exception, e:
                log.err("cannot decode json: %s" % str(e))
                log.err("json is: %s" % content)
            else:
                log.msg("got data ok: %s" % repr(data))

    def close(self):
        pass

if __name__ == "__main__":
    log.startLogging(sys.stdout)
    client.downloadPage("http://localhost:8888/c/collectd_data", CometClient())
    client.downloadPage("http://localhost:8888/c/collectd_event", CometClient())
    reactor.run()
