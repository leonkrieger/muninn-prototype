from pubsub import pub

def initiate():
    pub.sendMessage("status", message="ok")