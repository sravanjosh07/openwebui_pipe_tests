"""
SIMPLE MATH SERVER SECURITY CHECKER
==================================

This program does 3 things:
1. Starts a math server (that can do +, -, *, /, etc.)
2. Checks if each math operation is allowed using an API
3. Either allows or blocks the operation

Think of it like a security guard for math operations!
"""

import os
import sys
import json
import subprocess
import requests
from dotenv import load_dotenv

# Load settings from .env file
load_dotenv()

# =============================================================================
# SETTINGS (you can change these in your .env file)
# =============================================================================
API_URL = os.environ.get("AICEBERG_API_URL", "https://test.api.aiceberg.ai/eap/v0/event")
API_TOKEN = os.environ.get("AICEBERG_API_TOKEN", "YOUR_API_KEY")
PROFILE_ID = os.environ.get("AICEBERG_PROFILE_ID", "xxxx")
TIMEOUT_SECONDS = float(os.environ.get("AICEBERG_TIMEOUT_SECS", "0.8"))
ALLOW_ON_ERROR = os.environ.get("AICEBERG_FAIL_OPEN", "0") == "1"

print("🔧 Starting math server security checker...", file=sys.stderr)

# =============================================================================
# START THE MATH SERVER
# =============================================================================
# This starts the actual math server that can do calculations
math_server = subprocess.Popen(
    ["python", "math_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    bufsize=1
)

print("✅ Math server started!", file=sys.stderr)

# =============================================================================
# SECURITY CHECK FUNCTION
# =============================================================================
def is_operation_allowed(tool_name, tool_arguments):
    """
    Ask the security API: "Should I allow this math operation?"
    
    Args:
        tool_name: What operation? (like "add", "multiply", etc.)
        tool_arguments: What numbers? (like {"a": 5, "b": 3})
    
    Returns:
        "allow" or "block"
    """
    
    # Prepare the question for the security API
    question = f"TOOL: {tool_name}\nARGS: {json.dumps(tool_arguments)}"
    
    data_to_send = {
        "profile_id": PROFILE_ID,
        "input": question
    }
    
    try:
        # Ask the security API
        response = requests.post(
            API_URL,
            headers={
                "Content-Type": "application/json", 
                "Authorization": API_TOKEN
            },
            json=data_to_send,
            timeout=TIMEOUT_SECONDS,
        )
        
        # Get the answer
        if response.ok:
            answer = response.json()
        else:
            answer = {}
            
    except Exception as e:
        print(f"⚠️  Security API error: {e}", file=sys.stderr)
        # If API fails, decide what to do
        return "allow" if ALLOW_ON_ERROR else "block"
    
    # Check what the API said
    event_result = answer.get("event_result", "").lower()
    input_signal = answer.get("input_signal_result", "").lower()
    
    if event_result == "blocked" or input_signal == "block":
        return "block"
    else:
        return "allow"

# =============================================================================
# ERROR MESSAGE FUNCTION
# =============================================================================
def create_block_message(request_id, reason="Request blocked by security policy"):
    """
    Create an error message when we block an operation
    """
    error_response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32050,
            "message": "Request blocked by security policy",
            "data": {"reason": reason}
        }
    }
    return json.dumps(error_response)

# =============================================================================
# MAIN LOOP: CHECK EACH REQUEST
# =============================================================================
print("🛡️  Security checker is running. Monitoring math operations...", file=sys.stderr)

for incoming_line in sys.stdin:
    print(incoming_line)
    incoming_line = incoming_line.strip()
    
    # Try to understand the request
    try:
        request = json.loads(incoming_line)
    except:
        # If it's not a proper request, just pass it through
        math_server.stdin.write(incoming_line + "\n")
        math_server.stdin.flush()
        continue
    
    # Check if this is a request that needs an answer
    is_real_request = isinstance(request, dict) and ("id" in request)
    
    # Check if someone wants to use a math tool
    if is_real_request and request.get("method") == "tools/call":
        
        params = request.get("params", {})
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        print(f"🔍 Checking: {tool_name} with {tool_args}", file=sys.stderr)
        
        # Ask security API if this is allowed
        decision = is_operation_allowed(tool_name, tool_args)
        
        if decision == "block":
            print(f"🚫 BLOCKED: {tool_name}", file=sys.stderr)
            # Send error message back to client
            error_msg = create_block_message(request["id"])
            sys.stdout.write(error_msg + "\n")
            sys.stdout.flush()
            continue
        else:
            print(f"✅ ALLOWED: {tool_name}", file=sys.stderr)
    
    # If we get here, the request is allowed
    # Send it to the math server
    math_server.stdin.write(incoming_line + "\n")
    math_server.stdin.flush()
    
    # If this was a real request, wait for the math server's answer
    if is_real_request:
        answer = math_server.stdout.readline()
        if answer:
            sys.stdout.write(answer)
            sys.stdout.flush()

# =============================================================================
# CLEANUP
# =============================================================================
print("🔄 Shutting down...", file=sys.stderr)
math_server.terminate()