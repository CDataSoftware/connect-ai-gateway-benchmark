"""SSE-aware MCP JSON-RPC client for the endpoints under test.

Each endpoint is declared in the `endpoints:` block of config/models.yaml with its URL variable and
auth style:
  basic    Connect AI -- HTTP Basic with CDATA_EMAIL + CDATA_ACCESS_TOKEN.
  bearer   An MCP gateway -- a gateway key sent as `Authorization: Bearer <key>`.
"""
import base64, json, os, time, uuid
import requests

from core.heartbeat import beat


class MCPError(RuntimeError):
    pass


class MCPTimeout(MCPError):
    """A call ran past CALL_DEADLINE_S. Scored as a failed run, not retried as a harness error."""


# Total time allowed for one MCP call, response included. requests' timeout is per socket read, so a
# server-sent-event stream that stays open (keep-alives, or a connection lost without a close) can
# otherwise block a call indefinitely.
CALL_DEADLINE_S = 1800


def missing_env(ep):
    """Environment variables the endpoint needs that aren't set."""
    names = [ep["url_env"]]
    if ep["auth"] == "basic":
        names += ["CDATA_EMAIL", "CDATA_ACCESS_TOKEN"]
    elif ep["auth"] == "bearer":
        names.append(ep["key_env"])
    return [n for n in names if not os.environ.get(n)]


def endpoint_url(ep):
    return os.environ[ep["url_env"]].rstrip("/") + ep.get("path", "")


def connect(ep, timeout=90):
    """A client for one `endpoints:` entry, authenticated per its `auth` style."""
    if ep["auth"] == "basic":
        creds = base64.b64encode(
            f"{os.environ['CDATA_EMAIL']}:{os.environ['CDATA_ACCESS_TOKEN']}".encode()).decode()
        auth = {"Authorization": f"Basic {creds}"}
    elif ep["auth"] == "bearer":
        auth = {"Authorization": f"Bearer {os.environ[ep['key_env']]}"}
    else:
        raise MCPError(f"unknown endpoint auth {ep['auth']!r}")
    return MCPClient(endpoint_url(ep), auth, timeout=timeout)


class MCPClient:
    def __init__(self, base_url, auth_headers, timeout=90):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            **auth_headers,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self.timeout = timeout
        self.retries = 0
        self.retry_backoff_s = 0.0
        self.pending = None  # the tools/call in flight, kept if it never returns

    def _post(self, method, payload):
        # Retry transient network faults (DNS/connection drop, read timeout) with backoff so a
        # brief wifi blip mid-trajectory doesn't kill the whole run.
        for attempt in range(5):
            try:
                return requests.post(self.base_url, headers=self.headers, data=json.dumps(payload),
                                     timeout=self.timeout, stream=True)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt == 4:
                    raise MCPError(f"MCP {method} network error after retries: {str(e)[:200]}")
                wait = min(3 * (2 ** attempt), 30)
                self.retries += 1; self.retry_backoff_s += wait
                time.sleep(wait)

    def _rpc(self, method, params=None):
        beat(force=True)
        payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method}
        if params is not None:
            payload["params"] = params
        deadline = time.monotonic() + CALL_DEADLINE_S
        r = self._post(method, payload)
        if r.headers.get("Mcp-Session-Id"):
            self.headers["Mcp-Session-Id"] = r.headers["Mcp-Session-Id"]
        try:
            if r.status_code >= 400:
                raise MCPError(f"MCP {method} HTTP {r.status_code}: {self._read_body(method, r, deadline)[:300]}")
            if "text/event-stream" in r.headers.get("Content-Type", ""):
                # Event streams are UTF-8 by spec; without a declared charset requests would decode as ISO-8859-1.
                r.encoding = "utf-8"
                # return the first JSON-RPC message; don't wait for the stream to close
                for line in r.iter_lines(decode_unicode=True):
                    if time.monotonic() > deadline:
                        raise MCPTimeout(f"MCP {method}: no response within {CALL_DEADLINE_S}s")
                    line = (line or "").strip()
                    if line.startswith("data:"):
                        try:
                            return json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                raise MCPError(f"MCP {method}: no data line in SSE body")
            body = self._read_body(method, r, deadline)
            if "data:" in body:
                for line in body.splitlines():
                    line = line.strip()
                    if line.startswith("data:"):
                        try:
                            return json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                raise MCPError(f"MCP {method}: no data line in SSE body")
            return json.loads(body)
        except requests.exceptions.RequestException as e:
            raise MCPError(f"MCP {method} read failed: {str(e)[:200]}")
        finally:
            r.close()

    @staticmethod
    def _read_body(method, r, deadline):
        chunks = []
        for chunk in r.iter_content(chunk_size=65536):
            if time.monotonic() > deadline:
                raise MCPTimeout(f"MCP {method}: no complete response within {CALL_DEADLINE_S}s")
            chunks.append(chunk)
        return b"".join(chunks).decode(r.encoding or "utf-8", errors="replace")

    def initialize(self):
        res = self._rpc("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "benchmark-client", "version": "0.1.0"}})
        # The MCP spec's handshake. Connect AI doesn't require it; servers behind a gateway may.
        try:
            self._post("notifications/initialized",
                       {"jsonrpc": "2.0", "method": "notifications/initialized"}).close()
        except MCPError:
            pass
        return res

    def list_tools(self):
        res = self._rpc("tools/list", {})
        if "error" in res:
            raise MCPError(f"tools/list error: {res['error']}")
        return res.get("result", {}).get("tools", [])

    def call_tool(self, name, arguments):
        self.pending = {"tool": name, "arguments": arguments}
        res = self._rpc("tools/call", {"name": name, "arguments": arguments})
        beat(force=True)
        self.pending = None
        if "error" in res:
            return {"error": res["error"]}
        return res.get("result", {})

    @staticmethod
    def result_text(result, max_chars=8000):
        """Flatten a tools/call result to text, truncated."""
        if isinstance(result, dict) and "error" in result:
            body = json.dumps(result)
        else:
            parts = []
            for block in (result.get("content", []) if isinstance(result, dict) else []):
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            body = "\n".join(parts) if parts else json.dumps(result)
        if len(body) > max_chars:
            body = body[:max_chars] + " ...[truncated]"
        return body
