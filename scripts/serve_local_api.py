"""Local-only HTTP adapter for the existing Lambda entry point; no deployment."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'engine'), str(ROOT / 'lambda')]
from handler import lambda_handler
from api_http import MAX_BODY_BYTES


class LocalHandler(BaseHTTPRequestHandler):
    def handle_api(self):
        length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(min(length, MAX_BODY_BYTES + 1)).decode('utf-8', errors='replace') if length else None
        response = lambda_handler(dict(version='2.0', rawPath=self.path.split('?')[0],
                                       requestContext=dict(http=dict(method=self.command)),
                                       headers={name: self.headers[name] for name in ('Origin', 'Access-Control-Request-Method', 'Access-Control-Request-Headers') if self.headers.get(name)},
                                       body=body, isBase64Encoded=False), None)
        self.send_response(response['statusCode'])
        for name, value in response['headers'].items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(response['body'].encode('utf-8'))

    do_GET = do_POST = do_OPTIONS = handle_api

    def log_message(self, *_):
        pass  # Never log request bodies, headers or query strings.


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    os.environ.setdefault('GRIDMIND_ALLOWED_ORIGINS', '["http://localhost:5173","http://localhost:5174"]')
    print(f'Local GridMind API: http://localhost:{args.port} (no AWS deployment)', flush=True)
    ThreadingHTTPServer(('localhost', args.port), LocalHandler).serve_forever()
