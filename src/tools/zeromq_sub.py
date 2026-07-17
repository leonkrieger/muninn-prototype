import zmq, json
ctx = zmq.Context()
sock = ctx.socket(zmq.SUB)
sock.connect("tcp://192.168.178.125:5555")
sock.setsockopt_string(zmq.SUBSCRIBE, "delta-01/readings")

while True:
    topic, payload = sock.recv_multipart()
    print(topic.decode(), json.loads(payload.decode()))