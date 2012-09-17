#!/usr/bin/python
# coding: utf-8
# author: Eduardo S. Scarpellini, <scarpellini@gmail.com>

# You can uncomment bellow lines if you dont want to set PYTHONPATH
import sys, os
scriptdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append("%s/lib" % scriptdir)

import sys
import json
import myconfig
import dispatcher
from twisted.web import client
from twisted.python import log
from twisted.internet import reactor


class CometClient(object):
	def write(self, content):
		try:
			data = []
			content.rstrip()

			for line in content.split("\r\n"):
				if line:
					packet = json.loads(line)
					data.append( {"key": packet["key"], "value": json.loads(packet["value"])} )

		except Exception, err:
			log.err("Cannot decode JSON: %s" % str(err))
			log.err("MQ Return: %s" % content)
		else:
			for job in data:
				log.msg("*** Processing job \"%s\" ***" % job["key"])

				for task in job["value"].keys():
					log.msg("=> Dispatching task \"%s\"" % task)
					dispatcher.exe(task, job["value"][task])

	def close(self):
		pass


if __name__ == "__main__":
	cfg = myconfig.read()
	cfgvalues = cfg.restmq()

	log.startLogging(sys.stdout)

	client.downloadPage("http://%s:%s/c/%s" % (cfgvalues["host"], str(cfgvalues["port"]), cfgvalues["queuename"]), CometClient())
	reactor.run()
