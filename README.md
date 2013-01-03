# RestMQ Message Broker

    This is the source code of [RestMQ](http://restmq.com), by
    [Gleicon Moraes](https://github.com/gleicon) and
    [Alexandre Fiori](https://github.com/fiorix)


## About

RestMQ is a message broker. It uses HTTP as transport, and a minimalist JSON
protocol to manipulate queues.

Queues are created on the fly, when the first element is added to them. RestMQ
is extremely simple and easy to use.

### Dependencies

RestMQ is written in Python, and is confirmed to run on PyPy too.

Here's a list of what's required to run it:

- [Python](http://python.org) >= 2.5, or [PyPy](http://pypy.org) >= 1.8
- [Twisted](http://twistedmatrix.com/trac/) >= 10.0
- [cyclone](http://cyclone.io) >= 1.0-rc12
- [Redis](http://redis.io) >= 1.4

On Python 2.5, the [simplejson](http://pypi.python.org/pypi/simplejson/)
module is mandatory.

We recommend ``pip`` for installing Python dependencies:

    pip install simplejson twisted cyclone

And adjust *restmq.conf* for redis and other settings.

### Deployment

There's no need to install RestMQ. Just move this directory to /opt/restmq
and it should be good.

For production systems, we recommend running one RestMQ instance per CPU core,
and [Nginx](http://nginx.org) in front it load balancing the requests across
instances.

    Clients <-> Nginx <-> RestMQ CPU.1 127.0.0.1:9901
                          RestMQ CPU.2 127.0.0.1:9902
                          RestMQ CPU.3 127.0.0.1:9903
                          RestMQ CPU.4 127.0.0.1:9904

There are a couple of init.d scripts on the [scripts/](#) directory, for
starting one or multiple instances of RestMQ, and a sample configuration for
Nginx on [docs/README.nginx](#).

When using Nginx in front of RestMQ, you must edit *restmq.conf* and set
*xheaders = true*, otherwise all logs will appear as coming from 127.0.0.1.


## Overview

RestMQ treats HTTP clients as either producers or consumers. Generally
speaking, producers POST content to the server while consumers GET it.

It also supports live consumers, those with persistent connections to the
server, receiving new elements in real-time as they are created by producers.

Live consumers may connect to one of the following endpoints on RestMQ:

- Comet API, on */c/queue_name*
- WebSockets, on */ws/queue_name*
- SSE (not supported yet)

### Simple usage

1. Produce (store something on RestMQ)

    $ curl -d 'value=my element' http://localhost:8888/q/queue_name
    queue_name:1

2. Consume

    $ curl http://localhost:8888/q/queue_name
    {"count": 0, "key": "queue_name:1", "value": "my element"}

### Live consumers

Open two or more terminal consoles, and start live consumers via the Comet API:

    $ curl http://localhost:8888/c/queue_name

Then produce something, just like on the example above, and you should see it
immediately on all live consumers.

RestMQ support different queue policies for distributting new elements across
multiple live consumers: broadcast (the default), and round-robin. There are
more details on this below.

### Purging all elements of a queue

Queues may be purged anytime via the DELETE method:

    $ curl -X DELETE http://localhost:8888/q/queue_name
    {"queue": "queue_name", "status": 1}

*status* may be 0 if the queue is already empty or does not exist.


## Queue policies

Live consumers can keep a persistent connection to one or more queues on
RestMQ, and see new elements as they are created.

These consumers must be connected via the Comet API, WebSockets or SSE.

Consider the following scenario:

1. N consumers are connected to the "test" queue via the Comet API;
2. Random producers add elements to the "test" queue, and these elements are
   instantly delivered to consumers.

This helps on distributing elements of a queue across many consumers in real
time, and the queue policy determines how.

### Supported policies

Each queue on RestMQ has a policy for delivering content to consumers in real
time. The policy determines how new elements are distributed to these live
consumers.

Currently, only two policies are supported:

- Broadcast: the default policy for automatically created queues
- Round-robin: optional policy for real-time distributed systems

To see the policy of a queue:

    $ curl http://localhost:8888/p/queue_name
    {"queue": "queue_name", "value": "broadcast"}

#### Broadcast

This is the default distribution policy of all queues. When new elements are
added to a queue, they are automatically delivered to ALL live consumers.

Setting the broadcast policy:

    $ curl -d policy=broadcast http://localhost:8888/p/queue_name
    OK

#### Round-robin

This one is great for distributing the content of a queue across multiple
consumers, in a round-robin fashion. New content is always delivered to only
one consumer at a time.

Setting the round-robin policy:

    $ curl -d policy=roundrobin http://localhost:8888/p/queue_name
    OK


## Flow control

It's already there, and one day it'll be documented.


## Development

Looking for extending RestMQ? This is what's in this directory:

- ``start.sh``: simple shell script to start the development server
- ``restmq.conf``: RestMQ configuration file
- ``restmq/``: server code, starting on ``restmq/web.py``
- ``frontend/``: static files and HTML templates
- ``scripts/``: debian init scripts and other useful scripts

RestMQ uses a minimalist JSON protocol for controlling queues. JSON operations
are available on the /queue endpoint of the server.

Try /queue from a web browser and you'll get a simple form for interacting
directly with RestMQ via the JSON protocol.

All operations, however, are performed via HTTP POST on /queue.

It is a simple protocol for queue manipulation, based on my first prototype,
[jQueue](http://jsonqueue.appspot.com).

### Add

The following call adds an element to the given queue, which is created
if it does not exist.

    {
      "cmd":    "add",
      "queue":  "test",
      "value":  "oi"
    }

### Get

This call returns the next element in the queue, or an error.

    {
      "cmd":    "get",
      "queue":  "test"
    }

If the queue does not exist, it responds with:

    {
      "error":  "Null resultset"
    }

Otherwise:

    {
      "queue":  "test",
      "value":  "oi",
      "count":  1,
      "key":    "test:1"
    }

The ``get`` command does not remove the element from the queue. Instead, it
increments the number of times that the element has been requested - it's the
*count* element on the sample response above.

The *key* is a unique key that represents this very particular element on the
server. It's used to identify elements on operations like ``delete``.

### Delete

The following call deletes an element from the queue. It requires the
element's unique key, which is returned when the element is added to the
queue, or on the get command.

    {
      "cmd":    "del",
      "queue":  "test",
      "key":    "test:1"
    }

### Take

The ``take`` command get and remove the latest element from a given queue.
It is the ``get`` command followed by a ``delete``.

    {
      "cmd":    "take",
      "queue":  "test"
    }


## Credits
Thanks to (in no particular order):

- Salvatore Sanfilippo, for redis and for NoSQL patterns discussion.
- Alexandre Fiori, for the redis client enhancement and patches.
- Roberto Gaiser, for the collectd daemon
- <put your name here if you happen to send a patch>
