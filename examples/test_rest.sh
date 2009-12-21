#!/bin/bash

curl -X POST -d "queue=test&value=foobar" http://localhost:8888/
curl -X POST -d 'body={"cmd":"get", "queue":"test"}' http://localhost:8888/queue
curl -X POST -d "queue=test&value=foobar" http://localhost:8888/q/test
curl http://localhost:8888/q/test
#curl http://localhost:8888/?queue=test
