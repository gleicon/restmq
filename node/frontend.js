// RestMQ frontend for node.js
// provides comet and websockets route
// it doesnt polls as the original python version (due to internal hacking)
// ideas:   use pub/sub to speed new message handling
//          websockets !
// as there is no common proxy for ws and comet handling, a remote node.js node would help distributing load, security
// and of course, node.js is cool :D
// requires: http://github.com/fictorial/redis-node-client
// redis + node.js
//


var path = require("path");
var url = require("url");
var sys = require("sys");
var http = require("http");
var connections={};
var redis=require("./redis-node-client/lib/redis-client").createClient();

client.info(function (err, info) {
    if (err) throw new Error(err);
    sys.puts("Redis Version is: " + info.redis_version);
    client.close();
});


function hasProperties(o) { for (var p in o) if (o.hasOwnProperty(p)) return true; return false; }

function update() {
    if (hasProperties(connections)) {
        for (var c in connections) {
            sys.puts(connections[c].length);
            for (var q in connections[c]) {
                connections[c][q].sendBody('oi');
            }
        }
    }
    setTimeout(update, 1000);
}

setTimeout(update, 1000);
            
function addQueue(q, r) {
    if (connections[q] == null) {
        connections[q] = [];
    }
    connections[q].push(r);
}


http.createServer(function(req, res) {
        r = url.parse(req.url);
        queue = path.basename(r.pathname);
        if (path.dirname(r.pathname) == '/c') {
            req.connection.setTimeout(0); // endless comet
            res.sendHeader(200, {'Content-type':'text/plain'});
            addQueue(queue, res);
        } else {
            res.sendHeader(404, {'Content-type':'text/plain'});
            res.sendBody('not found');
            res.finish();
        }
        }).listen(8888);


