#!/usr/bin/python
# coding: utf-8
# author: Eduardo S. Scarpellini, <scarpellini@gmail.com>

import myloader

funcs = {
	"cpu": "dummyfuncs.generic",
	"mem": "dummyfuncs.generic",
	"load": "dummyfuncs.generic",
	"swap": "dummyfuncs.generic"
}

def exe(name, params):
	if funcs.has_key(name):
		try:
			func = myloader.myimport(funcs[name])
			func(params)
		except Exception, err:
			print "Error: %s" % err
	else:
		print "Error: No function for key \"%s\"" % name
