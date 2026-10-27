# SPDX-License-Identifier: Apache-2.0
# Minimal in-memory GitHub contents API for testing tools/gatherlane.py
import base64, json, hashlib, socketserver, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
FILES = {}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p = self.path.split('?')[0]
        if '/contents/' in p:
            k = p.split('/contents/')[1]
            if k in FILES: return self.send(200, {'content': base64.b64encode(FILES[k]).decode(), 'sha': hashlib.sha1(FILES[k]).hexdigest()})
            return self.send(404, {'message': 'Not Found'})
        if p == '/dump': return self.send(200, {k: json.loads(v) for k, v in FILES.items()})
        self.send(404, {'message': 'nope'})
    def do_PUT(self):
        k = self.path.split('/contents/')[1]
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if k in FILES and body.get('sha') != hashlib.sha1(FILES[k]).hexdigest(): return self.send(409, {'message': 'sha mismatch'})
        FILES[k] = base64.b64decode(body['content']); self.send(201, {})
FILES['control/pause.json'] = json.dumps({'schema': 'gatherlane.control/v1', 'paused': {'acme/social': {'since': 'x', 'by': 'maintainer', 'reason': 'holiday'}}}).encode()
class Server(HTTPServer):
    def server_bind(self):  # HTTPServer also looks up the host's FQDN here, which can take 35 s on macOS
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]
Server(('127.0.0.1', int(sys.argv[1])), H).serve_forever()
