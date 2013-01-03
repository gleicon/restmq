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


import base64
import cyclone.web
import cyclone.websocket
import cyclone.sse
import functools
import hashlib
import types

from ConfigParser import ConfigParser

from twisted.internet import reactor
from twisted.python import log


class TemplateFields(dict):
    """Helper class to make sure our
        template doesn't fail due to an invalid key"""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return None

    def __setattr__(self, name, value):
        self[name] = value


class BaseHandler(cyclone.web.RequestHandler):
    pass


class SmartHandler(object):
    def __init__(self, handler):
        self.handler = handler
        self.json_callback = handler.get_argument("callback", None)

    def write(self, text):
        if not isinstance(text, types.StringType):
            text = cyclone.escape.json_encode(text)

        if self.json_callback:
            text = "%s(%s);\r\n" % (self.json_callback, text)
        else:
            text = "%s\r\n" % text

        if isinstance(self.handler, cyclone.websocket.WebSocketHandler):
            self.handler.sendMessage(text)
        elif isinstance(self.handler, cyclone.sse.SSEHandler):
            self.handler.sendEvent(text)
        else:
            self.handler.write(text)

    def flush(self):
        self.handler.flush()

    def finish(self, text=None):
        if text:
            self.write(text)
        self.handler.finish()


class InvalidAddress(Exception):
    pass


class InvalidPassword(Exception):
    pass


def authorize(category):
    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            try:
                self.settings.acl.apply(self, category)
            except InvalidAddress:
                raise cyclone.web.HTTPError(401)  # Unauthorized
            except InvalidPassword:
                raise cyclone.web.HTTPAuthenticationRequired("Basic",
                                                "RestMQ Restricted Access")
            else:
                return method(self, *args, **kwargs)
        return wrapper
    return decorator


class ACL(object):
    def __init__(self, filename):
        self.md5 = None
        self.filename = filename

        self.rest_producer = {}
        self.rest_consumer = {}
        self.comet_consumer = {}
        self.websocket_consumer = {}
        self.sse_consumer = {}

        self.parse(True)

    def parse(self, firstRun=False):
        try:
            fp = open(self.filename)
            md5 = hashlib.md5(fp.read()).hexdigest()

            if self.md5 is None:
                self.md5 = md5
            else:
                if self.md5 == md5:
                    fp.close()
                    return

            fp.seek(0)
            cfg = ConfigParser()
            cfg.readfp(fp)
            fp.close()

        except Exception, e:
            if firstRun:
                raise e
            else:
                log.msg("ERROR: Could not reload configuration: %s" % e)
                return
        else:
            if not firstRun:
                log.msg("Reloading ACL configuration")

        for section in ("rest:producer",
                        "rest:consumer",
                        "comet:consumer",
                        "websocket:consumer",
                        "sse:consumer"):
            d = getattr(self, section.replace(":", "_"))

            try:
                hosts_allow = cfg.get(section, "hosts_allow")
                d["hosts_allow"] = hosts_allow.split() \
                                    if hosts_allow != "all" else None
            except:
                d["hosts_allow"] = None

            try:
                hosts_deny = cfg.get(section, "hosts_deny")
                d["hosts_deny"] = hosts_deny.split() \
                                    if hosts_deny != "all" else None
            except:
                d["hosts_deny"] = None

            try:
                username = cfg.get(section, "username")
                d["username"] = username
            except:
                d["username"] = None

            try:
                password = cfg.get(section, "password")
                d["password"] = password
            except:
                d["password"] = None

        reactor.callLater(60, self.parse)

    def check_password(self, client, username, password, websocket):
        try:
            if websocket is True:
                ruser, rpass = client.get_cookie("auth").split(":", 1)
            else:
                at, ad = client.request.headers["Authorization"].split()
                assert at == "Basic"
                ruser, rpass = base64.b64decode(ad).split(":", 1)

            assert username == ruser and password == rpass
        except:
            raise InvalidPassword

    def apply(self, client, category, websocket=False):
        acl = getattr(self, category)
        require_password = acl["username"] and acl["password"]

        if acl["hosts_allow"]:
            for ip in acl["hosts_allow"]:
                if client.request.remote_ip.startswith(ip):
                    if require_password:
                        self.check_password(client,
                            acl["username"], acl["password"], websocket)
                        return
                    else:
                        return

            if acl["hosts_deny"] is None:
                raise InvalidAddress("ip address %s not allowed" %
                                        client.request.remote_ip)

        if acl["hosts_deny"]:
            for ip in acl["hosts_deny"]:
                if client.request.remote_ip.startswith(ip):
                    raise InvalidAddress("ip address %s not allowed" %
                                            client.request.remote_ip)

        if require_password:
            self.check_password(client, acl["username"], acl["password"],
                                websocket)
