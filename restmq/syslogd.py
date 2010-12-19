#!/usr/bin/python
# -*- coding: utf-8 -*-

# launchctl unload /System/Library/LaunchDaemons/com.apple.syslogd.plist
# launchctl load /System/Library/LaunchDaemons/com.apple.syslogd.plist

from twisted.internet import reactor, defer
from twisted.internet.protocol import Protocol, ServerFactory
from twisted.protocols.basic import LineReceiver
import time, re, math, json, os
from restmq import core
import cyclone.redis


#<22>Nov  1 00:12:04 gleicon-vm1 postfix/smtpd[4880]: connect from localhost[127.0.0.1]
severity = ['emerg', 'alert', 'crit', 'err', 'warn', 'notice', 'info', 'debug', ]

facility = ['kern', 'user', 'mail', 'daemon', 'auth', 'syslog', 'lpr', 'news',
    'uucp', 'cron', 'authpriv', 'ftp', 'ntp', 'audit', 'alert', 'at', 'local0',
    'local1', 'local2', 'local3', 'local4', 'local5', 'local6', 'local7',]

fs_match = re.compile("<(.+)>(.*)", re.I)

class SyslogdProtocol(LineReceiver):
    delimiter = '\n'
    def connectionMade(self):
        print 'Connection from %r' % self.transport

    def lineReceived(self, line):
        host = self.transport.getHost().host
        queue_name = "syslogd:%s" % host
        k = {}
        k['line'] = line.strip()
        (fac, sev) = self._calc_lvl(k['line'])
        k['host'] = host
        k['tstamp'] = time.time()
        k['facility'] = fac
        k['severity'] = sev
        self.factory.oper.queue_add(queue_name, json.dumps(k))

    def _calc_lvl(self, line):
        lvl = fs_match.split(line)
        if lvl and len(lvl) > 1:
            i = int(lvl[1])
            fac = int(math.floor(i / 8))
            sev = i - (fac * 8)
            return (facility[fac], severity[sev])
        return (None, None)

class SyslogdFactory(ServerFactory):
    protocol = SyslogdProtocol

    def __init__ (self, redis_host, redis_port, redis_pool, redis_db ):

        db = cyclone.redis.lazyRedisConnectionPool(
            redis_host, redis_port,
            pool_size=redis_pool, db=redis_db)

        self.oper = core.RedisOperations(db)

