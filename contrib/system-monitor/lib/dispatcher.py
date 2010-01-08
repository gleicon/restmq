#!/usr/bin/python
# coding: utf-8
# author: Eduardo S. Scarpellini, <scarpellini@gmail.com>

import myconfig
import myloader


def exe(name, params):
	cfg = myconfig.read()
	cfgvalues = cfg.dispatcher()

	if cfgvalues.has_key(name):
		try:
			func = myloader.myimport(cfgvalues[name])
			func(params)
		except Exception, err:
			print "Error: %s" % err
	else:
		print "Error: No function for key \"%s\"" % name
