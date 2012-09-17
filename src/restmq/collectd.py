# coding: utf-8

import os.path
import cyclone.web
import cyclone.redis

import pkg_resources as pkg

from twisted.python import log
from twisted.internet import defer

from restmq import core

import json
import web

class CollectdRestQueueHandler(web.RestQueueHandler):

    @web.authorize("rest_producer")
    @defer.inlineCallbacks
    def post(self, queue):
        value = self.request.body
        if value is None:
            raise cyclone.web.HTTPError(400)
        if queue == 'data':
            content_type = self.request.headers.get('Content-Type')
            queue = 'collectd_data'
            if content_type == 'text/plain':
                try:
                    value = value.splitlines()
                    value = self.collectd_plaintext_parser(value)
                    value = json.dumps(value)
                except Exception, e:
                    log.msg("ERROR: %s" % e)
                    raise cyclone.web.HTTPError(503)
            elif content_type == 'application/json':
                pass
            else:
                log.msg("ERROR: Content-Type not expected %s" % content_type)
                raise cyclone.web.HTTPError(503)
        elif queue == 'event':
            queue = 'collectd_event'
            try:
                value = value.splitlines()
                event = value.pop()
                value = value[:-1]
                value = self.collectd_plaintext_parser(value)
                value.append({'event_text': event})
                value = json.dumps(value)
            except Exception, e:
                log.msg("ERROR: %s" % e)
                raise cyclone.web.HTTPError(503)
        else:
            raise cyclone.web.HTTPError(400)
        callback = self.get_argument("callback", None)

        try:
            result = yield self.settings.oper.queue_add(queue, value)
        except Exception, e:
            log.msg("ERROR: oper.queue_add('%s', '%s') failed: %s" % (queue, value, e))
            raise cyclone.web.HTTPError(503)

        if result:
            self.settings.comet.queue.put(queue)
            web.CustomHandler(self, callback).finish(result)
        else:
            raise cyclone.web.HTTPError(400)

    def collectd_plaintext_parser(self,lines):
        event_protocol = {'Severity': None,
                'Time': None,
                'Host': None,
                'Plugin': None,
                'Type': None,
                'TypeInstance': None,
                'DataSource': None,
                'CurrentValue': None,
                'WarningMin': None,
                'WarningMax': None,
                'FailureMin': None,
                'FailureMax': None,}
        collectd_data = []
        for line in lines:
            line = line.split(' ')
            if line[0] == 'PUTVAL':
                (host,plugin_instance,type_instance) = line[1].split('/')
                interval = line[2].split('=')[1]
                value = line[3]
                collectd_data.append({'host':host,
                   'plugin_instance':plugin_instance,
                   'type_instance':type_instance,
                   'interval':interval,'value':value})
            elif line[0].rstrip(':') in event_protocol:
                key = line[0].rstrip(':').lower()
                value = line[1]
                collectd_data.append({key: value})
        return collectd_data

class Collectd(web.Application):

    def __init__(self, acl_file, redis_host, redis_port, redis_pool, redis_db):
        handlers = [
            (r"/",       web.IndexHandler),
            (r"/q/(.*)", web.RestQueueHandler),
            (r"/c/(.*)", web.CometQueueHandler),
            (r"/p/(.*)", web.PolicyQueueHandler),
            (r"/j/(.*)", web.JobQueueInfoHandler),
            (r"/stats/(.*)",  web.StatusHandler),
            (r"/queue",  web.QueueHandler),
            (r"/control/(.*)",  web.QueueControlHandler),
            (r"/ws/(.*)",  web.WebSocketQueueHandler),
        ]

        handlers.append((r"/collectd/(.*)", CollectdRestQueueHandler))

        try:
            acl = web.ACL(acl_file)
        except Exception, e:
            log.msg("ERROR: Cannot load ACL file: %s" % e)
            raise RuntimeError("Cannot load ACL file: %s" % e)

        db = cyclone.redis.lazyConnectionPool(
            redis_host, redis_port,
            poolsize=redis_pool, dbid=redis_db)

        oper = core.RedisOperations(db)
        
        settings = {
            "db": db,
            "acl": acl,
            "oper": oper,
            "comet": web.CometDispatcher(oper),
            "static_path": pkg.resource_filename('restmq', 'static'),
            "template_path": pkg.resource_filename('restmq', 'templates'),
        }

        cyclone.web.Application.__init__(self, handlers, **settings)
