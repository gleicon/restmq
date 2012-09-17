On HTTP clients
===============

Most of the examples for RestMQ are using either curl or urllib. The reason is that I wanted to show how simple is to interact with the broker. 

Real life is that you might find out clients that will be more restrict or lax regarding content type or headers.


POSTing data
====

In general, methods that receive data via POST need to specify the 'application/x-www-form-urlencoded' content-type.

On examples that use curl, this is already set in as you use the -d key (highlight is mine):


  $ curl -vvv -X POST -d "value=foobar" http://localhost:8888/q/test
  * About to connect() to localhost port 8888 (#0)
  *   Trying ::1... Connection refused
  *   Trying 127.0.0.1... connected
  * Connected to localhost (127.0.0.1) port 8888 (#0)
  > POST /q/test HTTP/1.1
  > User-Agent: curl/7.21.4 (universal-apple-darwin11.0) libcurl/7.21.4 OpenSSL/0.9.8r zlib/1.2.5
  > Host: localhost:8888
  > Accept: */*
  > Content-Length: 12
  *> Content-Type: application/x-www-form-urlencoded*
  > 
  < HTTP/1.1 200 OK
  < Content-Length: 11
  < Content-Type: text/html; charset=UTF-8
  < Server: cyclone/1.0-rc6
  < 
  test:1003
  * Connection #0 to host localhost left intact
  * Closing connection #0

For urllib usually we construct the request like this:

    def post_in_queue(subject, author, text):                                       
        try:                                                                        
            msg={'subject': subject, 'author':author, 'text':text}                  
            *data = urllib.urlencode({'queue':'twitter', 'value':json.dumps(msg)})*
            r = urllib2.Request('http://localhost:8888/', data)
            f = urllib2.urlopen(r)                                                  
            data = f.read()                                                         
            f.close()                                                               
        except urllib2.URLError, e:                                                 
            print e.code                                                            
            print e.read()                                                          
        print data

Using Python Requests (http://docs.python-requests.org/):

    import requests                                                                                                                                                 
                                                                                    
    payload = {'value': 'el requesto',}                                             
    r = requests.post("http://localhost:8888/q/test", data=payload)                 
    print r.text

If you dont pass a dict to data, it will behave a bit like a PUT request.

GETting data
============

GET methods will bind to URIs like single messages ('/q/queuename') or COMET stream ('/c/queuename').
If you client support connection pools, you should be probably be using them for long term connections. 
Check if they recicle and if your queue  has a broadcast or roundrobin policy set. 
You can set roundrobin and receive a new message per connection.
No special header is needed but take care of the return codes.


