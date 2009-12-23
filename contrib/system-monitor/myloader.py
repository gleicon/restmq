#!/usr/bin/python
# coding: utf-8
# author: Eduardo S. Scarpellini, <scarpellini@gmail.com>

def myimport(name):
	components = name.split(".")

	try:
		attrref = __import__(components[0])

		for component in components[1:]:
			attrref = getattr(attrref, component)
	except Exception, err:
		print "Error: %s" % err
	else:
		return attrref
