#!/usr/bin/python
# coding: utf-8
# author: Eduardo S. Scarpellini, <scarpellini@gmail.com>

import sys
import simplejson
import dispatcher
from twisted.web import client
from twisted.python import log
from twisted.internet import reactor

RESTMQ_HOST = "localhost"
RESTMQ_PORT = 8888
QUEUENAME   = "monitor"

class CometClient(object):
	def write(self, content):
		try:
                        packet = simplejson.loads(content)
			data = simplejson.loads(packet["value"])
			jobid = packet['key'] 
		except Exception, err:
			log.err("Cannot decode JSON: %s" % str(err))
			log.err("MQ Return: %s" % content)
		else:
                        log.msg("processing job: %s " % jobid)
			for key in data.keys():
				log.msg("Dispatching key \"%s\"" % key)
				dispatcher.exe(key, data[key])

	def close(self):
		pass

if __name__ == "__main__":
	log.startLogging(sys.stdout)
	client.downloadPage("http://%s:%s/c/%s" % (RESTMQ_HOST, str(RESTMQ_PORT), QUEUENAME), CometClient())
	reactor.run()
