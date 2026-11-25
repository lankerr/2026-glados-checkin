"""Feed a local sample ledger to the same entry point as the daily report."""
import json
import os
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import patch

import checkin
import update_streak


def main():
    now = checkin.beijing_now()
    history = [
        {"time": int((now - timedelta(days=days)).timestamp() * 1000),
         "business": label, "change": amount}
        for days, label, amount in [
            (0, "system:checkin", 4), (1, "compensation", 3), (2, "system:checkin", 2)
        ]
    ]
    payload = json.dumps({"points": 37, "history": history}).encode()
    calls = []

    class LedgerHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append((self.command, self.path))
            if self.path != "/api/user/points":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    with HTTPServer(("127.0.0.1", 0), LedgerHandler) as server:
        worker = Thread(target=server.serve_forever)
        worker.start()
        try:
            origin = f"http://127.0.0.1:{server.server_port}"
            fixture_env = {"GLADOS_COOKIE": "gld:sess=demo; gld:sess.sig=demo"}
            with patch.object(checkin, "DOMAINS", [origin]), patch.dict(os.environ, fixture_env, clear=True):
                result = update_streak.main()
        finally:
            server.shutdown()
            worker.join()
    if result or calls != [("GET", "/api/user/points")]:
        raise RuntimeError(f"Unexpected ledger read: {calls}")
    print("Demo: GET /api/user/points (loopback), 1 request")


if __name__ == "__main__":
    main()
