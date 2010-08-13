# Sinatra minimalist RestMQ
# no COMET, just /q/ routes and queue logic
# the core of RestMQ is how it uses Redis' data types

require 'rubygems'
require 'sinatra'
require 'redis'

QUEUESET = 'QUEUESET'   # queue index
UUID_SUFFIX = ':UUID'   # queue unique id
QUEUE_SUFFIX = ':queue' # suffix to identify each queue's LIST

reds = Redis.new

get '/q/*' do
  queue = params['splat'].to_s
  throw :halt, [404, 'Not found\n'] if queue == nil
  queue = queue + QUEUE_SUFFIX
  b = reds.rpop queue
  throw :halt, [404, 'Not found (empty queue)\n'] if b == nil
  v = reds.get b
  "{'value':" + v + "'key':" + b + "}" 
end

post '/q/*' do
  queue = params['splat'].to_s
  value = params['value'].to_s
  throw :halt, [404, "Not found"] if queue == nil
  q1 = queue + QUEUE_SUFFIX
  uuid = reds.incr queue + UUID_SUFFIX 
  reds.sadd QUEUESET, q1
  lkey = queue + ':' + uuid.to_s
  reds.set lkey, value
  reds.lpush q1, lkey
  '{ok, '+lkey+'}'
end
