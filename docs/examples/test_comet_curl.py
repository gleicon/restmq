#! /usr/bin/env python
# -*- coding: utf-8 -*-

#
# Usage: python test-comet-curl.py <url> [No of simultaneous connections]
# Example: python test-comet-curl.py http://localhost:8888/c/test 100
# Adapted from retrieve-multi.py from PyCurl library
#
 
import sys
import pycurl

def pretty_printer(who):#, buf):
#    print "%s: %s" %(who)#, buf)
    print "-> %s" %(who)

try:
    import signal
    from signal import SIGPIPE, SIG_IGN
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)
except ImportError:
    pass


# Get args
num_conn = 10

try:
    if len(sys.argv) < 2:
        print "Needs a URL"
        sys.exit(-1)
    url = sys.argv[1]
    print url
    if len(sys.argv) >= 3:
        num_conn = int(sys.argv[2])
except Exception, e:
    print e
    print "Usage: %s <url> [No of simultaneous connections]" % sys.argv[0]
    raise SystemExit



assert 1 <= num_conn <= 10000, "invalid number of concurrent connections"
print "PycURL %s (compiled against 0x%x)" % (pycurl.version, pycurl.COMPILE_LIBCURL_VERSION_NUM)
print "----- Getting", url, "URLs using", num_conn, "connections -----"


# Pre-allocate a list of curl objects
m = pycurl.CurlMulti()
m.handles = []
for i in range(num_conn):
    c = pycurl.Curl()
    c.fp = None
    c.setopt(pycurl.FOLLOWLOCATION, 1)
    c.setopt(pycurl.MAXREDIRS, 5)
    c.setopt(pycurl.CONNECTTIMEOUT, 30)
    c.setopt(pycurl.TIMEOUT, 300)
    c.setopt(pycurl.NOSIGNAL, 1)
    m.handles.append(c)


# Main loop
freelist = m.handles[:]
num_processed = 0
while num_processed < num_conn:
    while freelist:
        c = freelist.pop()
        c.setopt(pycurl.URL, url)
#        c.setopt(pycurl.WRITEFUNCTION, pretty_printer)
        m.add_handle(c)

    while 1:
        ret, num_handles = m.perform()
        if ret != pycurl.E_CALL_MULTI_PERFORM:
            break

    while 1:
        num_q, ok_list, err_list = m.info_read()
        for c in ok_list:
            c.fp.close()
            c.fp = None
            m.remove_handle(c)
            print "Success:", c.filename, c.url, c.getinfo(pycurl.EFFECTIVE_URL)
            freelist.append(c)
        for c, errno, errmsg in err_list:
            c.fp.close()
            c.fp = None
            m.remove_handle(c)
            print "Failed: ", c.filename, c.url, errno, errmsg
            freelist.append(c)
        num_processed = num_processed + len(ok_list) + len(err_list)
        if num_q == 0:
            break
    m.select(1.0)


# Cleanup
for c in m.handles:
    if c.fp is not None:
        c.fp.close()
        c.fp = None
    c.close()
m.close()

