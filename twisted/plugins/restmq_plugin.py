#!/usr/bin/env python
# coding: utf-8

from zope.interface import implements
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application import service, internet

import restmq.web

class Options(usage.Options):
    optParameters = [
        ["redis-host", "", "127.0.0.1", "hostname or ip address of the redis server"],
        ["redis-port", "", 6379, "port number of the redis server"],
        ["redis-pool", "", 10, "connection pool size"],
        ["port", "", 8888, "port number to listen on"],
        ["listen", "", "127.0.0.1", "interface to listen on"],
    ]

class ServiceMaker(object):
    implements(service.IServiceMaker, IPlugin)
    tapname = "restmq"
    description = "A RESTful Message Broker"
    options = Options

    def makeService(self, options):
        return internet.TCPServer(options["port"],
            restmq.web.Application(options["redis-host"], options["redis-port"], options["redis-pool"]),
            interface=options["listen"])

serviceMaker = ServiceMaker()
