======
RESTMQ
======

Redis based message queue.
--------------------------

:Info: See `RestMQ website <http://restmq.com>`_
:Info: See `my blog <http://blog.7co.cc>` for more information.
:Author: `Gleicon Moraes <http://github.com/gleicon>`
:Author: `Alexandre Fiori <http://github.com/fiorix/>`_


About
=====

RestMQ is a message queue which uses HTTP as transport, JSON to format a minimalist protocol and is organized as REST
resources. It stands on the shoulder of giants, built over Python, Twisted, `Cyclone <http://github.com/fiorix/cyclone>`_ (a Tornado implementation over twisted) and Redis.

Redis is more than just a key/value db, and its data types provided support for this project.

Queues are created on the fly, when a message is sent to them. They are simple to use as a curl request can be. HTTP Comet, websockets and server sent events may be used for data streaming.

This release is a cleanup of the original code, that can also be found on github.

Install
=======

$ python setup.py install
run with bash start_scripts/restmq_server or taylor your own script. Note that currently restmq is presented as a twisted plugin.

Alternatively you can utilize [Vagrant](https://www.vagrantup.com/) and our [Vagrantfile](Vagrantfile) which will handle installation and configuration of redis and RestMQ.

Another option is to run the project inside a docker container:

```
docker build -t restmq .
docker run --rm  -p 6379:6379 -p 8888:8888 restmq
```

It will run restmq, exposing both 8888 (for its http port) and 6379 (for its redis server) to the host environment.

Queue Policy
============

Every queue is created with a default policy, which is `broadcast`. It means that each message
pushed to a queue will be forwarded to all comet and websocket consumers.

The alternative policy is `roundrobin`, which will distribute these messages in a round robin
fashion to all comet and websocket consumers.

The queue policy won't affect regular GET commands to pop a single message from a queue.

See `README.qp <http://github.com/gleicon/restmq/blob/master/README.qp>`_ for details.


Queue Flow Control
==================

Yes, it does support start and stop. We just need to document it properly.


Example
========
A http client (curl) post to /queue:

Point your browser to http://localhost:8888/c/test

Run $ curl -d "queue=test&value=foobar" http://localhost:8888/

Your browser is acting as a consumer to the queue. Using json encoded data it's easy to fit the data into a js based app.

Aside from the COMET consumer, there are xmlrpc methods, rest routes and the JSON protocol to manipulate queue items.


COMET consumer
==============

There is a COMET based consumer, which will bind even if the queue doesn't already exists.

The main route is thru /c/<queuename>. It can be tested using curl:

$ curl http://localhost:8888/c/test

In another terminal, run $ curl -d "value=foobar" http://localhost:8888/q/test

This is the basic usage pattern for map/reduce (see examples).

See below on how to purge and disconnect all consumers from a queue, using DELETE.


WebSocket consumer
==================

Now that cyclone has websockets support, check README.websocket to test it.

If you are using a browser or library which already supports websockets, you may take advantage of this interface.


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
- Persistent storage using Redis
- Can work on pools, N daemons consuming from the same queues.
- Small codebase
- Lightweight
- Cute ?


Dependencies
============
- `cyclone <http://github.com/fiorix/cyclone>`_:
  git clone git://github.com/fiorix/cyclone.git


Running
=======

The `redis_server <http://github.com/gleicon/restmq/blob/master/restmq_server>`_ script will start the service. It's a bash script used to both configure and run RestMQ. The default version of the wrapper script will run the server in foreground, and log messages will be written to the standard output.

Editing the script is mandatory for configuring RestMQ for production.

::

    $ ./restmq_server --help
    Usage: twistd [options] restmq [options]
    Options:
          --acl=         acl configuration file for endpoints [default: acl.conf]
          --redis-host=  hostname or ip address of the redis server [default: 127.0.0.1]
          --redis-port=  port number of the redis server [default: 6379]
          --redis-pool=  connection pool size [default: 10]
          --port=        port number to listen on [default: 8888]
          --listen=      interface to listen on [default: 127.0.0.1]
          --version
          --help         Display this help and exit.


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

If you're a developer looking for extending RestMQ's functionality, have a look at these files:

- `restmq/web.py <http://github.com/gleicon/restmq/blob/master/restmq/web.py>`_: the web service code
- `restmq/core.py <http://github.com/gleicon/restmq/blob/master/restmq/core.py>`_: redis/queue operations logic
- `restmq/dispatch.py <http://github.com/gleicon/restmq/blob/master/restmq/dispatch.py>`_: a simple command dispatcher
- `restmq_engine.py <http://github.com/gleicon/restmq/blob/master/restmq_engine.py>`_: the redis abstraction layer to the queue algorithm (command line tool)


Credits
=======
Thanks to (in no particular order):

- Salvatore Sanfilippo for redis and for NoSQL patterns discussion.
- Alexandre Fiori for the redis client enhancement and patches.
- Roberto Gaiser for the collectd daemon
- Vitor Pellegrino for dockerizing restmq
