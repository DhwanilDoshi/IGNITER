import http.server
import socketserver
import os

PORT = 8001

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving folder: {BASE_DIR}")
    print(f"Open in browser: http://localhost:{PORT}")
    httpd.serve_forever()
