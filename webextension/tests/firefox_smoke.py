"""Opt-in QA: python firefox_smoke.py FIREFOX_BINARY GECKODRIVER FIREFOX_ZIP.
Requires Selenium and cryptography. A loopback TLS fixture serves all site data.
"""
import argparse
import datetime
import json
import socketserver
import ssl
import tempfile
import threading
import time
import uuid
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


def tls_context(folder):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'glados.cloud')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(hours=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('glados.cloud')]), critical=False)
            .sign(key, hashes.SHA256()))
    pem = folder / 'fixture.pem'
    pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM) + key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(pem)
    return ctx


def fixture(tls, requests):
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(8)
            method_host = self.rfile.readline(4096).split()
            if method_host[:2] != [b'CONNECT', b'glados.cloud:443']:
                self.wfile.write(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
                return
            while self.rfile.readline(8192).strip():
                pass
            self.wfile.write(b'HTTP/1.1 200 Connection established\r\n\r\n')
            try:
                with tls.wrap_socket(self.connection, server_side=True) as client, client.makefile('rb') as stream:
                    line = stream.readline(4096).decode().split()
                    if len(line) != 3:
                        return
                    method, path, _ = line
                    while stream.readline(8192).strip():
                        pass
                    requests.append((method, path))
                    mime = 'application/json'
                    if path == '/api/user/status':
                        body = json.dumps({'code':'0', 'data':{'email':'qa@example.test'}})
                    elif path == '/api/user/points':
                        body = json.dumps({'code':'0', 'points':'17', 'history':[{
                            'time':int(time.time()*1000)-1000, 'business':'system:checkin','change':2}]})
                    else:
                        mime = 'text/html'
                        body = '<!doctype html><title>Local Firefox fixture</title>'
                    data = body.encode()
                    client.sendall(f'HTTP/1.1 200 OK\r\nContent-Type: {mime}\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n'.encode() + data)
            except OSError:
                pass  # Firefox may close speculative connections.
    return Handler


def run(binary, geckodriver, archive, screenshot=None):
    addon = 'checkin-desk@lankerr.github.io'
    internal_id = str(uuid.uuid4())
    requests = []
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        xpi = folder / 'desk.xpi'
        xpi.write_bytes(archive.read_bytes())
        with socketserver.ThreadingTCPServer(('127.0.0.1', 0), fixture(tls_context(folder), requests)) as server:
            server.daemon_threads = True
            threading.Thread(target=server.serve_forever, daemon=True).start()
            options = Options()
            options.binary_location = str(binary)
            options.add_argument('-headless')
            options.accept_insecure_certs = True
            options.set_preference('extensions.webextensions.uuids', json.dumps({addon:internal_id}))
            options.set_preference('network.proxy.type', 1)
            for scheme in ('http', 'ssl'):
                options.set_preference('network.proxy.' + scheme, '127.0.0.1')
                options.set_preference('network.proxy.' + scheme + '_port', server.server_address[1])
            try:
                # Recent Firefox releases require this driver option to navigate
                # directly to a locally installed moz-extension test page.
                service = Service(str(geckodriver), service_args=['--allow-system-access'])
                with webdriver.Firefox(options=options, service=service) as driver:
                    assert driver.install_addon(str(xpi), temporary=True) == addon
                    driver.get('moz-extension://' + internal_id + '/console.html')
                    wait = WebDriverWait(driver, 12)
                    element = lambda key: driver.find_element(By.ID, key)
                    wait.until(lambda _: element('open').is_enabled())
                    assert not requests
                    desk = driver.current_window_handle
                    element('open').click()
                    wait.until(lambda _: len(driver.window_handles) == 2)
                    site = next(handle for handle in driver.window_handles if handle != desk)
                    driver.switch_to.window(site)
                    wait.until(lambda _: driver.title == 'Local Firefox fixture')
                    driver.switch_to.window(desk)
                    element('refresh').click()
                    wait.until(lambda _: element('open').is_enabled())
                    assert element('points').text == '17', (element('feedback').text, requests)
                    assert 'q•••@example.test' in element('account').text
                    assert element('status').text == driver.execute_script("return browser.i18n.getMessage('confirmed')")
                    if screenshot:
                        if not driver.save_screenshot(str(screenshot)):
                            raise OSError("Could not save the Firefox screenshot")
                    element('reminder').click()
                    wait.until(lambda _: element('open').is_enabled())
                    assert driver.execute_async_script("const done=arguments[0];browser.alarms.get('daily-reminder').then(a => done(!!a));")
                    assert requests and all(method == 'GET' for method, _ in requests)
                    print('PASS Firefox', driver.capabilities['browserVersion'], 'temporary install, official page, confirmed ledger, masked identity, reminder.')
            finally:
                server.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('binary','geckodriver','archive'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()
    run(args.binary.resolve(), args.geckodriver.resolve(), args.archive.resolve(), args.screenshot)
