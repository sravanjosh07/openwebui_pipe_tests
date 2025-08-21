import os, sys, json, subprocess, requests
from dotenv import load_dotenv
load_dotenv()

# --- Minimal config via environment ---
API_URL   = os.environ.get("AICEBERG_API_URL", "https://test.api.aiceberg.ai/eap/v0/event")
API_TOKEN = os.environ.get("AICEBERG_API_TOKEN", "YOUR_API_KEY")
PROFILE   = os.environ.get("AICEBERG_PROFILE_ID", "xxxx")
TIMEOUT   = float(os.environ.get("AICEBERG_TIMEOUT_SECS", "0.8"))
FAIL_OPEN = os.environ.get("AICEBERG_FAIL_OPEN", "0") == "1"  # 1 = allow on API failure

# --- Start the real MCP math server as a child process (STDIO transport) ---
proc = subprocess.Popen(
    ["python", "math_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    bufsize=1  # line-buffered
)
assert proc.stdin and proc.stdout

def post_decision(tool_name, tool_args):
    """Return 'allow' or 'block' from the Aiceberg API."""
    payload = {
        "profile_id": PROFILE,
        "input": f"TOOL: {tool_name}\nARGS: {json.dumps(tool_args, separators=(',',':'))}"
    }
    try:
        r = requests.post(
            API_URL,
            headers={"Content-Type": "application/json", "Authorization": API_TOKEN},
            json=payload,
            timeout=TIMEOUT,
        )
        data = r.json() if r.ok else {}
    except Exception:
        return "allow" if FAIL_OPEN else "block"

    event_result = (data.get("event_result") or "").lower()
    input_signal = (data.get("input_signal_result") or "").lower()
    if event_result == "blocked" or input_signal == "block":
        return "block"
    return "allow"  # treat 'flagged' as allow for v1

def block_error(req_id, reason="Request blocked by policy"):
    """JSON-RPC error with implementation-defined code (-32000..-32099)."""
    return json.dumps(
        {"jsonrpc":"2.0","id":req_id,
         "error":{"code":-32050,"message":"Request blocked by policy","data":{"reason":reason}}}
    )

# --- Main loop: read client line -> maybe check -> forward or block -> relay reply ---
for line in sys.stdin:
    line = line.rstrip("\n")

    # Try to parse JSON. If not JSON, just pass through (and don't wait for a reply).
    try:
        obj = json.loads(line)
    except Exception:
        proc.stdin.write(line + "\n"); proc.stdin.flush()
        continue

    is_request_with_id = isinstance(obj, dict) and ("id" in obj)

    # Gate only tools/call (requests with an id)
    if is_request_with_id and obj.get("method") == "tools/call":
        p = obj.get("params", {})
        if post_decision(p.get("name"), p.get("arguments", {})) == "block":
            sys.stdout.write(block_error(obj["id"]) + "\n"); sys.stdout.flush()
            continue

    # Allowed -> forward to real server
    proc.stdin.write(line + "\n"); proc.stdin.flush()

    # Only wait for a reply if the client sent a request with an id (not a notification)
    if is_request_with_id:
        out = proc.stdout.readline()
        if out:
            sys.stdout.write(out); sys.stdout.flush()

# Clean up when client closes
proc.terminate()