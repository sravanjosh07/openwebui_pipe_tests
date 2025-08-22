"""
MCP Math Proxy — simple & readable

This proxy does four things:
1) Starts the math MCP server as a subprocess
2) Logs the handshake and every method (calls & notifications)
3) Checks tool calls against a tiny policy (allow/block)
4) Forwards JSON-RPC between client and server (stdout stays pure JSON)
"""

import os
import sys
import json
import subprocess
from dotenv import load_dotenv

load_dotenv()

# These are kept for future API integration (not used in the toy policy below)
API_URL = os.environ.get("AICEBERG_API_URL", "https://test.api.aiceberg.ai/eap/v0/event")
API_TOKEN = os.environ.get("AICEBERG_API_TOKEN", "YOUR_API_KEY")
PROFILE_ID = os.environ.get("AICEBERG_PROFILE_ID", "xxxx")
TIMEOUT_SECONDS = float(os.environ.get("AICEBERG_TIMEOUT_SECS", "0.8"))
ALLOW_ON_ERROR = os.environ.get("AICEBERG_FAIL_OPEN", "0") == "1"

SERVER_CMD = ["python", "math_server.py"]

# Small logging helper (stderr only; stdout must be pure JSON-RPC)
def log(msg: str) -> None:
    print(msg, file=sys.stderr)

log("🔧 Starting math server security checker…")

# Start math server subprocess (stdio transport)
math_server = subprocess.Popen(
    SERVER_CMD,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    bufsize=1,
)
log("✅ Math server started!")

def create_block_message(request_id, reason: str = "Request blocked by security policy") -> str:
    """Return JSON-RPC error for a blocked request."""
    return json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32050,
            "message": "Request blocked by security policy",
            "data": {"reason": reason},
        },
    })


def is_operation_allowed(tool_name: str | None, tool_arguments: dict) -> str:
    """Toy policy: block if the string '9' appears anywhere in the serialized request."""
    question = f"TOOL: {tool_name}\nARGS: {json.dumps(tool_arguments)}"
    return "block" if "9" in question else "allow"


def is_call(msg: dict) -> bool:
    """JSON-RPC request that expects a response (has id)."""
    return isinstance(msg, dict) and (msg.get("id") is not None) and ("method" in msg)


def is_notification(msg: dict) -> bool:
    """JSON-RPC notification (no id)."""
    return isinstance(msg, dict) and (msg.get("id") is None) and ("method" in msg)


log(" Security checker running. Monitoring math operations…")

for incoming_line in sys.stdin:
    line = incoming_line.strip()

    # Try to parse JSON; if not JSON, pass-through
    try:
        request = json.loads(line)
    except Exception:
        if math_server.stdin:
            math_server.stdin.write(line + "\n")
            math_server.stdin.flush()
        continue

    method = request.get("method")
    req_id = request.get("id")

    # Classify & log
    if is_call(request):
        log(f"← client CALL {method} id={req_id}")
    elif is_notification(request):
        log(f"← client NOTE {method} id=None")
    else:
        log("← client (unknown frame)")

    if method == "initialize" and is_call(request):
        # continue
        params = request.get("params", {})
        log(f"initialize → {json.dumps(params)}")
    elif method == "notifications/initialized" and is_notification(request):
        log("notifications/initialized received — client is ready")

    if is_call(request) and method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        log(f"🔍 Checking: {tool_name} {tool_args}")

        decision = is_operation_allowed(tool_name, tool_args)
        if decision == "block":
            log(f"BLOCKED: {tool_name}")
            sys.stdout.write(create_block_message(req_id) + "\n")
            sys.stdout.flush()
            continue
        else:
            log(f"ALLOWED: {tool_name}")

    current_method = method
    if math_server.stdin:
        math_server.stdin.write(line + "\n")
        math_server.stdin.flush()

    if is_call(request):
        answer = math_server.stdout.readline() if math_server.stdout else ""
        if answer:
            try:
                resp = json.loads(answer.strip())
                status = "OK" if "result" in resp else "ERR"
                log(f"→ server RESP {current_method} id={resp.get('id')} {status}")
            except Exception:
                pass

            if current_method == "initialize":
                try:
                    init_resp = json.loads(answer.strip())
                    if "result" in init_resp:
                        result = init_resp["result"]
                        proto = result.get("protocolVersion")
                        caps = list(result.get("capabilities", {}).keys())
                        server_info = result.get("serverInfo") or {}
                        server_name = server_info.get("name")
                        server_version = server_info.get("version")
                        log(f"initialize result ← protocol={proto} caps={caps} server={server_name} {server_version}")
                except Exception as e:
                    log(f" Could not parse initialize result: {e}")

            sys.stdout.write(answer)
            sys.stdout.flush()


log("Shutting down…")
math_server.terminate()