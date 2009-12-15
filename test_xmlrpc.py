#!/usr/bin/env python
# coding: utf-8

import xmlrpclib

srv = xmlrpclib.Server("http://localhost:8888/xmlrpc")
print "set:", srv.set("test", "tuna-boy")
print "get:", srv.get("test")
