======
RESTMQ
======

Redis based message queue.
--------------------------

:Info: See `my blog <http://zenmachine.wordpress.com>`_ for more information.
:Author: Gleicon Moraes <gleicon@gmail.com>
:Author: Alexandre Fiori


About
=====
RestMQ is a message queue which uses HTTP as transport, JSON to format a minimalist protocol and is organized as REST 
resources. It stands on the shoulder of giants, built over Python, Twisted, Cyclone (a Tornado implementation over twisted) and Redis.

Redis is more than just a key/value db, and its data types provided support for this project.

The queues are created on the fly, as a message is sent to them. They are simple to use as a curl request can be.



Example
========
A http client (curl) post to /queue:

Point your browser to http://localhost:8888/c/test

Run $ curl -X POST -d "queue=test&value=foobar" http://localhost:8888/ 

Your browser is acting as a consumer to the queue. Using json encoded data it's easy to fit the data into a js based app.

Aside from the COMET consumer, there are xmlrpc methods, rest routes and the JSON protocol to manipulate queue items.


COMET consumer
==============

There is a COMET based consumer, which will bind even if the queue doesn't already exists. 

The main route is thru /c/<queuename>, It can be tested using curl:

$ curl http://localhost:8888/c/test

In another terminal, run $ curl -X POST -d "queue=test&value=foobar" http://localhost:8888/ 

This is the basic usage pattern for map/reduce (see examples).

See below on how to purge and disconnect all consumers from a queue, using DELETE.



REST services
=============

A queue can be accessed as /q/<queuename>.

GET requests will dequeue an object.

POST requests inserts an object in the queue

DELETE requests will purgue the queue.

The usual pattern is listen in the COMET consumer (/c/<queuename>) and insert new stuff at the REST route (POST /q/<queuename).


JSON Protocol
=============

The HTTP route /queue/<queuename> uses the JSON protocol. Its the same protocol I've implemented for http://jsonqueue.appspot.com.

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

- Select, EPoll or KQueue concurrency (depends on twisted)
- Persistent queueing using Redis
- Can work on pools, N daemons consuming from the same queues.
- Cute ?
- Small codebase


Dependencies
============
- python, twisted
- `redis client <http://github.com/fiorix/txredisapi>`_: 
  git clone git://github.com/fiorix/txredisapi.git
- `cyclone <http://github.com/fiorix/cyclone>`_: 
  git clone git://github.com/fiorix/cyclone.git 


Running
=======
Development environment:

::

    twistd -ny restmq_server.tac

Production environment (needs epoll and proper user/group): 

::

    twistd --pidfile=/var/run/restmq.pid --logfile=/var/log/restmq.log \
           --reactor=epoll --uid=www-data --gid=www-data --python=restmq_server.tac


Tests
=====

::

    examples/test_rest.sh
    examples/test_xmlrpc.py
    python examples/test_comet.py
    python examples/twitter_trends.py
    python examples/test_comet_curl.py  
    python restmq_engine.py -h


Files
=====
- restmq/dispatch.py: - a simple command dispatcher
- restmq_engine.py: the redis abstraction layer to the queue algorithm
- restmq_server.tac - the main app (a web service)


Credits
=======
Thanks to (in no particular order):
    Salvatore Sanfilippo for redis and for NoSQL patterns discussion.
    Alexandre Fiori for the redis client enhancement and patches.
