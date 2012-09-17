#!/usr/bin/python
# coding: utf-8
# author: Eduardo S. Scarpellini, <scarpellini@gmail.com>

# You can uncomment bellow lines if you dont want to set PYTHONPATH
import sys, os
scriptdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append("%s/lib" % scriptdir)

import urllib, urllib2
import json
import myconfig
import simplemonitor


def post_data(host, port, queuename):
	try:
		params = urllib.urlencode({"queue":queuename, "value":json.dumps(simplemonitor.get_all_values())})

		request = urllib2.Request("http://%s:%s" % (host, str(port)), params)
		f = urllib2.urlopen(request)

		response = f.read()

		f.close()
	except urllib2.URLError, err:
		print err
	else:
		print "MQ Response: %s" % response


if __name__ == "__main__":
	cfg = myconfig.read()
	cfgvalues = cfg.restmq()

	post_data(cfgvalues["host"], cfgvalues["port"], cfgvalues["queuename"])
