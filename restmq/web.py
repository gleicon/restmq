# coding: utf-8
#
# Copyright 2009 Gleicon Moraes
# Powered by cyclone
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


import cyclone.web

from restmq import utils
from restmq import views
from restmq import config
from restmq.storage import DatabaseMixin

from twisted.python import log


class Application(cyclone.web.Application):
    def __init__(self, config_file):
        handlers = [
            (r"/",                  views.IndexHandler),
            (r"/queue",             views.RawQueueHandler),
            (r"/q/(.*)",            views.RestQueueHandler),
            (r"/p/(.*)",            views.PolicyQueueHandler),
            (r"/j/(.*)",            views.JobQueueInfoHandler),
            (r"/control/(.*)",      views.QueueControlHandler),
            (r"/stats/(.*)",        views.StatusHandler),

            # Live consumers
            (r"/c/(.*)",            views.CometConsumerHandler),
            (r"/ws/(.*)",           views.WebSocketConsumerHandler),
            (r"/sse/(.*)",          views.SSEConsumerHandler),
        ]

        conf = config.parse_config(config_file)

        try:
            conf["acl"] = utils.ACL(conf["acl_file"])
        except Exception, e:
            log.msg("ERROR: Cannot load ACL file: %s" % e)
            raise RuntimeError("Cannot load ACL file: %s" % e)

        # Set up database connections
        DatabaseMixin.setup(conf)

        conf["autoescape"] = None
        cyclone.web.Application.__init__(self, handlers, **conf)
