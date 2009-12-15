#!/usr/bin/env python
# coding: utf-8
# twistd -ny restmq.tac
# twisted/cyclone app skeleton copycat from fiorix's webredis.tac (http://fiorix.wordpress.com)
# gleicon moraes (http://zenmachine.wordpress.com | http://github.com/gleicon)

from restmq import web
from twisted.application import service, internet

application = service.Application("restmq")
srv = internet.TCPServer(8888, web.Application())
srv.setServiceParent(application)
