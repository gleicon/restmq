#!/usr/bin/python
# coding: utf-8
# author: Eduardo S. Scarpellini, <scarpellini@gmail.com>

def generic(data):
	for key in data.keys():
		print " - [dummy] Value for key \"%s\": %s" % (key, data[key])
