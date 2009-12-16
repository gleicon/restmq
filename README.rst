======
RESTMQ
======

Redis based message queue.
--------------------------

:Info: See `the redis site <http://code.google.com/p/redis/>`_ for more information.
:Author: Gleicon Moraes <gleicon@gmail.com>

About
=====
RestMQ is a message queue which uses HTTP as transport, JSON to format a minimalist protocol and is organized as REST 
resources. It stands on the shoulder of giants, built over Python, Twisted and Redis.

The queues are created on the fly, as a message is sent to them.

Example
========

A http client (curl) post to /queue:

::

    {
        "cmd": "add",
        "queue": "genesis",
        "value": "abacab"
    }

Creates the queue named *"genesis"* and inserts the string *"abacab"* as the message.

If we want to take that out of the queue, the payload would be like that:

::

    {
        "cmd": "take",
        "queue": "genesis"
    }


The message can be formatted as a json object, so more complex data can be sent.
It really mimics some of `Amazon SQS <http://aws.amazon.com/sqs/>`_ workings, because it's a simple queue.

For the first release it has:

- EPoll or KQueue concurrency
- Persistent queueing using redis
- Can work on pools, N daemons consuming from the same queues.
- Cute ?
- Small code




Dependencies
============

- python, twisted
- `redis client <http://github.com/fiorix/txredisapi>`_: 
  git clone git://github.com/fiorix/txredisapi.git
- `cyclone <http://github.com/fiorix/tornado>`_: 
  git clone git://github.com/fiorix/tornado.git 

Running
=======

Development environment:
::
    twistd -ny restmq.tac

Production environment (needs epoll and proper user/group): 
::
    twistd --pidfile=/var/run/restmq.pid --logfile=/var/log/restmq.log \
           --reactor=epoll --uid=www-data --gid=www-data --python=restmq_server.tac

Tests
=====
::
    examples/test_rest.sh
    examples/test_xmlrpc.py
    python restmq_engine.py -h

Files
=====
- restmq/dispatch.py: - a simple command dispatcher
- restmq_engine.py: the redis abstraction layer to the queue algorithm
- restmq_server.tac - the main app (a web service)

Credits
=======
Thanks to (in no particular order):

- Alexandre Fiori
    - Testing, coding, etc
