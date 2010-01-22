#!/bin/bash

curl -X POST -d "queue=test&value=foobar" http://localhost:8888/
curl -X POST -d 'body={"cmd":"get", "queue":"test"}' http://localhost:8888/queue
curl -X POST -d "queue=test&value=foobar" http://localhost:8888/q/test
curl http://localhost:8888/q/test
#curl http://localhost:8888/?queue=test

curl http://localhost:8888/control/test
curl -X POST -d "status=stop" http://localhost:8888/control/test
curl http://localhost:8888/control/test
curl -X POST -d "status=start" http://localhost:8888/control/test
curl http://localhost:8888/control/test
curl http://localhost:8888/c/test &
curl -X DELETE http://localhost:8888/q/test

