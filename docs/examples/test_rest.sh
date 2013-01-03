#!/bin/bash

echo "QUEUE DATA"
curl -X POST -d "queue=test&value=foobar" http://localhost:8888/
curl -X POST -d 'body={"cmd":"get", "queue":"test"}' http://localhost:8888/queue
curl -X POST -d "value=foobar" http://localhost:8888/q/test
curl http://localhost:8888/q/test
echo
echo "QUEUE CONTROL"
curl http://localhost:8888/control/test
curl -X POST -d "status=stop" http://localhost:8888/control/test
curl http://localhost:8888/control/test
curl -X POST -d "status=start" http://localhost:8888/control/test
curl http://localhost:8888/control/test
curl -X DELETE http://localhost:8888/q/test
echo
echo "QUEUE POLICY"
curl http://localhost:8888/p/test
curl -D - -X POST -d "policy=roundrobin" http://localhost:8888/p/test
curl http://localhost:8888/p/test
curl -D - -X POST -d "policy=broadcast" http://localhost:8888/p/test
curl http://localhost:8888/p/test

echo
echo "COMET (send something from other term with curl -X POST -d 'value=foobar' http://localhost:8888/q/test)"
curl http://localhost:8888/c/test 

