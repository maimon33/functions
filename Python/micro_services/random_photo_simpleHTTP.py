import os
import sys
import random
import SimpleHTTPServer

import SocketServer as socketserver

class MyHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    path_to_image = ''

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "image/jpg")
        self.end_headers()
        random_pic = '{}{}'.format(
            self.path_to_image,
            random.choice(os.listdir(self.path_to_image)))
        print random_pic
        f = open(random_pic, 'rb')
        self.wfile.write(f.read())
        f.close()

if __name__ == "__main__":
    try:
        MyHandler.path_to_image = sys.argv[1]
        server = socketserver.TCPServer(("", 8080), MyHandler)
        server.serve_forever()
    except IndexError:
        print "Missing PATH to folder"
    except KeyboardInterrupt:
        print "Server stopped"