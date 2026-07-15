import base64
import json
import os
import random
import shutil
import socket
import struct
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CHROME = Path(os.environ.get("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe"))
BASE_URL = os.environ.get("ADMIN_DEBUG_URL", "http://127.0.0.1:8000/admin.html")
EMAIL = os.environ.get("ADMIN_DEBUG_EMAIL", "")
PASSWORD = os.environ.get("ADMIN_DEBUG_PASSWORD", "")
PORT = int(os.environ.get("ADMIN_DEBUG_PORT", "9227"))
PROFILE = ROOT / ".tmp" / "chrome-admin-debug"


class CdpWs:
    def __init__(self, ws_url):
        parsed = urlparse(ws_url)
        self.host = parsed.hostname
        self.port = parsed.port
        self.path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        response = self.sock.recv(4096)
        if b"101" not in response.splitlines()[0]:
            raise RuntimeError(f"WebSocket handshake failed: {response[:200]!r}")
        self.next_id = 1
        self.events = []

    def _recv_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise RuntimeError("WebSocket closed")
            data += chunk
        return data

    def recv(self, timeout=0.2):
        self.sock.settimeout(timeout)
        try:
            header = self._recv_exact(2)
        except socket.timeout:
            return None
        b1, b2 = header
        opcode = b1 & 0x0F
        masked = b2 & 0x80
        length = b2 & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        if opcode == 8:
            raise RuntimeError("WebSocket closed by browser")
        if opcode == 1:
            return json.loads(payload.decode("utf-8"))
        return None

    def send_json(self, payload):
        data = json.dumps(payload).encode("utf-8")
        mask = os.urandom(4)
        length = len(data)
        frame = bytearray([0x81])
        if length < 126:
            frame.append(0x80 | length)
        elif length < 65536:
            frame.append(0x80 | 126)
            frame.extend(struct.pack("!H", length))
        else:
            frame.append(0x80 | 127)
            frame.extend(struct.pack("!Q", length))
        frame.extend(mask)
        frame.extend(bytes(byte ^ mask[i % 4] for i, byte in enumerate(data)))
        self.sock.sendall(frame)

    def call(self, method, params=None, timeout=10):
        msg_id = self.next_id
        self.next_id += 1
        self.send_json({"id": msg_id, "method": method, "params": params or {}})
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.recv(timeout=0.5)
            if not msg:
                continue
            if msg.get("id") == msg_id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            self.events.append(msg)
        raise TimeoutError(method)

    def drain(self, seconds=1):
        deadline = time.time() + seconds
        while time.time() < deadline:
            msg = self.recv(timeout=0.1)
            if msg:
                self.events.append(msg)


def wait_json(url, timeout=12):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            time.sleep(0.25)
    raise RuntimeError(f"DevTools not ready: {last}")


def js_string(value):
    return json.dumps(value)


def main():
    if not EMAIL or not PASSWORD:
        raise SystemExit("Defina ADMIN_DEBUG_EMAIL e ADMIN_DEBUG_PASSWORD para executar o debug de login.")
    if not CHROME.exists():
        raise SystemExit(f"Chrome nao encontrado: {CHROME}")
    if PROFILE.exists():
        shutil.rmtree(PROFILE)
    PROFILE.mkdir(parents=True, exist_ok=True)

    args = [
        str(CHROME),
        "--headless=new",
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={PROFILE}",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/json/new?{urllib.request.pathname2url(BASE_URL)}",
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            target = json.loads(response.read().decode("utf-8"))
        ws_url = target["webSocketDebuggerUrl"]
        cdp = CdpWs(ws_url)
        cdp.call("Runtime.enable")
        cdp.call("Page.enable")
        cdp.call("Network.enable")
        nav = cdp.call("Page.navigate", {"url": BASE_URL})
        ready = None
        for _ in range(40):
            time.sleep(0.25)
            cdp.drain(0.05)
            try:
                ready_eval = cdp.call(
                    "Runtime.evaluate",
                    {"expression": "document.readyState + '|' + location.href + '|' + document.body.children.length", "returnByValue": True},
                    timeout=2,
                )
                ready = ready_eval.get("result", {}).get("value")
                if ready and ready.startswith("complete|") and not ready.endswith("|0"):
                    break
            except Exception:
                pass

        fill_and_click = f"""
(() => {{
  const email = document.getElementById('adminEmail');
  const pass = document.getElementById('adminPassword');
  const btn = document.getElementById('adminLoginButton');
  if (!email || !pass || !btn) return {{ok:false, reason:'login elements missing', html: document.body.innerText.slice(0, 300)}};
  email.value = {js_string(EMAIL)};
  pass.value = {js_string(PASSWORD)};
  email.dispatchEvent(new Event('input', {{bubbles:true}}));
  pass.dispatchEvent(new Event('input', {{bubbles:true}}));
  btn.click();
  return {{ok:true, buttonText: btn.textContent}};
}})()
"""
        before_click = cdp.call(
            "Runtime.evaluate",
            {
                "expression": "({ready:document.readyState,url:location.href,body:document.body.innerText.slice(0,200),hasEmail:Boolean(document.getElementById('adminEmail')),scripts:[...document.scripts].map(s=>s.src)})",
                "returnByValue": True,
            },
        )
        click_result = cdp.call("Runtime.evaluate", {"expression": fill_and_click, "returnByValue": True})
        time.sleep(18)
        cdp.drain(1)

        state_expr = """
(() => ({
  url: location.href,
  adminLoginHidden: document.getElementById('adminLogin')?.hidden,
  adminAppHidden: document.getElementById('adminApp')?.hidden,
  buttonText: document.getElementById('adminLoginButton')?.textContent,
  buttonDisabled: document.getElementById('adminLoginButton')?.disabled,
  loginErrorHidden: document.getElementById('loginError')?.hidden,
  loginErrorText: document.getElementById('loginError')?.textContent,
  viewTitle: document.getElementById('viewTitle')?.textContent,
  statusNotice: document.getElementById('statusNotice')?.textContent,
  hasToken: Boolean(localStorage.getItem('mdl_admin_token')),
  sessionUser: (() => { try { return JSON.parse(localStorage.getItem('mdl_admin_user') || '{}')?.email } catch { return null } })(),
  bodyClass: document.body.className,
  adminLoginDisplay: getComputedStyle(document.getElementById('adminLogin')).display,
  adminAppDisplay: getComputedStyle(document.getElementById('adminApp')).display,
  scriptSrc: [...document.scripts].map(s => s.src).filter(Boolean)
}))()
"""
        state = cdp.call("Runtime.evaluate", {"expression": state_expr, "returnByValue": True})
        events = cdp.events
        console_events = [
            event.get("params", {})
            for event in events
            if event.get("method") in {"Runtime.consoleAPICalled", "Runtime.exceptionThrown", "Log.entryAdded"}
        ]
        network_events = [
            event.get("params", {})
            for event in events
            if event.get("method") in {"Network.requestWillBeSent", "Network.loadingFailed", "Network.responseReceived", "Network.loadingFinished"}
        ]
        interesting_network = []
        for params in network_events:
            response = params.get("response") or {}
            request = params.get("request") or {}
            url = response.get("url") or request.get("url") or params.get("requestId")
            if "auth/login" in str(url) or "admin" in str(url):
                interesting_network.append(params)
        print(json.dumps({
            "navigate": nav,
            "ready": ready,
            "before_click": before_click.get("result", {}).get("value"),
            "click_result": click_result.get("result", {}).get("value"),
            "state": state.get("result", {}).get("value"),
            "console": console_events[-20:],
            "network": interesting_network[-60:],
        }, ensure_ascii=False, indent=2))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
