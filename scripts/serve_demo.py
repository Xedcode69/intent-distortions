"""Serve only the standalone educational demo, with no API or production secrets."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import argparse

class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        super().end_headers()

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--port",type=int,default=3001);args=parser.parse_args()
    directory=Path(__file__).resolve().parents[1]/"demo"
    print(f"Educational demo: http://127.0.0.1:{args.port} (synthetic data; no credentials)",flush=True)
    ThreadingHTTPServer(("127.0.0.1",args.port),partial(Handler,directory=str(directory))).serve_forever()
