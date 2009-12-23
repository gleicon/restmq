#!/usr/bin/python
# coding: utf-8
# author: Eduardo S. Scarpellini, <scarpellini@gmail.com>

import urllib, urllib2
import simplemonitor

RESTMQ_HOST = "localhost"
RESTMQ_PORT = 8888
QUEUENAME   = "monitor"

def post_data():
	try:
		params = urllib.urlencode({"queue":QUEUENAME, "value":simplemonitor.get_all_values()})

		request = urllib2.Request("http://%s:%s" % (RESTMQ_HOST, str(RESTMQ_PORT)), params)
		f = urllib2.urlopen(request)

		response = f.read()

		f.close()
	except urllib2.URLError, err:
		print err
	else:
		print "MQ Response: %s" % response


if __name__ == "__main__":
        post_data()
