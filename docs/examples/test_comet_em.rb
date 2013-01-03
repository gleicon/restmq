require 'rubygems'
require 'eventmachine'
require 'em-http'
require 'json'

# the traditional EM http client doesn't handle COMET requests well 
# (it may have some undocumented feature as twisted's downloadPage which you can fool by sending a class with a fake write() method)
# in any case its here, if someone is willing to fix it :)
#
#
#EventMachine.run do
#  include EM::Protocols
#  conn = HttpClient2.connect('localhost', 8888)

#  req = conn.get('/q/test')
#  req.callback do
#    p(req.content)
#    EM.stop
#  end
#end

# 
# an approach like this could do, but demands http header processing...
#
#class CometSubscriber < EventMachine::Connection
#    def initialize(*args)
#        super
#        send_data "GET /c/test HTTP/1.1\r\nHost: localhost:8888\r\n\r\n"
#    end
#     
#    def receive_data(data)
#        p data
#    end
#end
#
#EventMachine::run do 
#    EventMachine::connect 'localhost', 8888, CometSubscriber
#end

# then I came thru EM-HTTP-Client, which does it very well
# source: http://github.com/igrigorik/em-http-request
#
# gem install eventmachine
# gem install em-http-request
# gem install json
#
EventMachine.run {
    http = EventMachine::HttpRequest.new('http://localhost:8888/c/test').get
    http.stream { |chunk| 
        d = JSON::parse chunk
        c = d.to_hash
        print "original: #{chunk}"
        print "key: "+ c['key']+"\n"
        print "value: "+c['value']+"\n"
    }
}

