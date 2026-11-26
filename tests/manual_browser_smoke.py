"""Run manually: python tests/manual_browser_smoke.py (Chrome, Playwright, openssl)."""
import json
import ssl
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
import browser_checkin as browser


class Site(BaseHTTPRequestHandler):
    posts = 0
    def log_message(self, *args): pass

    def send(self, content, content_type):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        self.wfile.write(content.encode())

    def do_GET(self):
        if self.path == '/api/user/status':
            self.send(json.dumps({'data': {'email': 'qa@example.invalid'}}), 'application/json')
        elif self.path == '/console/checkin':
            # Exercise the network guard twice in the real browser.
            self.send("""<script>setTimeout(()=>{for(let i=0;i<2;i++)
                fetch('/api/user/checkin',{method:'POST'}).catch(()=>{});},500)</script>""", 'text/html')
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != '/api/user/checkin':
            self.send_error(404)
            return
        Site.posts += 1
        self.send(self.server.reply, 'application/json')


def main():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        key, cert = root/'key.pem', root/'cert.pem'
        conf = root/'openssl.cnf'
        conf.write_text('[req]\ndistinguished_name=dn\n[dn]\n', encoding='ascii')
        subprocess.run(['openssl', 'req', '-config', str(conf), '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-subj', '/CN=localhost', '-days', '1', '-keyout', str(key), '-out', str(cert)],
                       check=True, stderr=subprocess.DEVNULL)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cert, key)
        site = ThreadingHTTPServer(('127.0.0.1', 0), Site)
        site.socket = tls.wrap_socket(site.socket, server_side=True)
        origin = f'https://127.0.0.1:{site.server_port}'
        threading.Thread(target=site.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw, patch.object(browser, 'DOMAINS', (origin,)), patch.object(browser, 'RESULT_WAIT_SECONDS', 8):
                instance = pw.chromium.launch(channel='chrome', headless=True)
                for reply, pending in [('{"code":"0","message":"Checkin!"}', False), ('bad JSON', True)]:
                    ctx = instance.new_context(ignore_https_errors=True, service_workers='block')
                    try:
                        marker = root/'pending'
                        site.reply = reply
                        before = Site.posts
                        res = browser._manual_page(ctx, 'gld:sess=fake; gld:sess.sig=fake', 'qa@example.invalid', marker)
                        ctx.pages[0].wait_for_timeout(200)
                        assert Site.posts == before + 1 and marker.exists() == pending, (Site.posts, res)
                        assert (res.get('reason') == 'submission-unknown') if pending else res.get('code') == '0'
                    finally:
                        ctx.close()
                instance.close()
        finally:
            site.shutdown()
            site.server_close()
    print('PASS: loopback HTTPS, at most one POST, known/unknown outcomes and marker state.')


if __name__ == '__main__':
    main()
