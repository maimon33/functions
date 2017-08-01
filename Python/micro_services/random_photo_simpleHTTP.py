import SimpleHTTPServer
import SocketServer as socketserver
import os
import random

class MyHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    path_to_image = '/pictures_folder'

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
    server = socketserver.TCPServer(("", 8080), MyHandler)
    server.serve_forever()