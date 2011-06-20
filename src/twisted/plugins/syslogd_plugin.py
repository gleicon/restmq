#!/usr/bin/env python
# coding: utf-8

from zope.interface import implements
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application import service, internet

import restmq.syslogd

class Options(usage.Options):
    optParameters = [
        ["redis-host", "", "127.0.0.1", "hostname or ip address of the redis server"],
        ["redis-port", "", 6379, "port number of the redis server", int],
        ["redis-pool", "", 10, "connection pool size", int],
        ["redis-db", "", 0, "redis database", int],
        ["port", "", 25000, "port number to listen on", int],
        ["listen", "", "127.0.0.1", "interface to listen on"],
    ]

class ServiceMaker(object):
    implements(service.IServiceMaker, IPlugin)
    tapname = "syslogd"
    description = "Syslogd RESTful Message Broker"
    options = Options

    def makeService(self, options):
        return internet.TCPServer(options["port"],
            restmq.syslogd.SyslogdFactory(options["redis-host"], options["redis-port"],
                options["redis-pool"], options["redis-db"]),
            interface=options["listen"])

serviceMaker = ServiceMaker()
