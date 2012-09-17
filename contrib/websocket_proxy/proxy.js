var net = require('net');
var sys = require('sys');

function repr(wot) {
  sys.puts(sys.inspect(wot));
}

net.createServer(function (socket) {
  //repr(socket);
  client = net.createConnection(8888);
  socket.setEncoding('utf-8');
  client.setEncoding('utf-8');

  socket.addListener("connect", function () {
    sys.log("Connection from " + socket.remoteAddress+" Port: " + socket.remotePort);
  });

  // 1.0.101 and experimental git HEAD sys.pump
  sys.pump(socket, client);
  sys.pump(client, socket);

  socket.addListener("end", function () {
    sys.log("Connection from " + socket.remoteAddress+" Port: " + socket.remotePort +" has ended");
    socket.end();
  });

  
}).listen(9000);

