import os
import re
import time
import base64
import shutil
import zipfile
import subprocess
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer


USERNAME_PASSWORD = 'admin:password'


class S(BaseHTTPRequestHandler):
    key = ''
    
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        self.wfile.write("Hi from Python!")

    def do_AUTHHEAD(self):
        print "send header"
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"Test\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
    def do_POST(self):
        ''' Present frontpage with user authentication. '''
        if self.headers.getheader('Authorization') == None:
            self.do_AUTHHEAD()
            self.wfile.write('no auth header received')
            pass

        elif self.headers.getheader('Authorization') == 'Basic ' + self.key :
            self._set_headers()
            self.wfile.write('authenticated!')
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            self.wfile.write('\nSuccessfully POSTed {}\n'.format(post_data))

        else:
            self.do_AUTHHEAD()
            self.wfile.write(self.headers.getheader('Authorization'))
            self.wfile.write('not authenticated')
            pass

def run(server_class=HTTPServer, handler_class=S, port=8000):
    S.key = base64.b64encode(USERNAME_PASSWORD)
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print 'Starting httpd...'
    httpd.serve_forever()



if __name__ == "__main__":
    run()
