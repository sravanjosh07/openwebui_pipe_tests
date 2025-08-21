"""
GIT OPERATIONS SECURITY PROXY
=============================

This program protects a Git MCP server that can:
- Read Git repository information
- Show Git logs and diffs
- Execute Git commands
- Access file contents through Git

Our security layer checks each Git operation before allowing it.
This demonstrates proxying around a REAL publicly available MCP server!
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

print("🔧 Starting Git operations security proxy...", file=sys.stderr)

# =============================================================================
# START THE GIT MCP SERVER (publicly available!)
# =============================================================================
# This starts the real mcp-server-git package we just installed
git_server = subprocess.Popen(
    ["python", "-m", "mcp_server_git", "."],  # "." means current directory
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    bufsize=1
)

print("✅ Git MCP server started!", file=sys.stderr)

# =============================================================================
# SECURITY CHECK FUNCTION
# =============================================================================
def is_git_operation_allowed(tool_name, tool_arguments):
    """
    Ask the security API: "Should I allow this Git operation?"
    
    Git operations can be sensitive because:
    - git_log could reveal commit history and author information
    - git_diff could show sensitive code changes
    - git_show_file could access any file in the repository
    - git_search could find sensitive strings in code
    
    Args:
        tool_name: What operation? (like "git_log", "git_diff", etc.)
        tool_arguments: What parameters? (like {"path": "secrets.txt"})
    
    Returns:
        "allow" or "block"
    """
    
    # Create a detailed question for the security API
    question = f"GIT_OPERATION: {tool_name}\nARGS: {json.dumps(tool_arguments)}"
    
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
        # If API fails, be careful with Git operations
        return "allow" if ALLOW_ON_ERROR else "block"
    
    # Check what the API said
    event_result = answer.get("event_result", "").lower()
    input_signal = answer.get("input_signal_result", "").lower()
    
    if event_result == "blocked" or input_signal == "block":
        return "block"
    else:
        return "allow"

# =============================================================================
# GIT OPERATION RISK ANALYZER
# =============================================================================
def analyze_git_risk(tool_name, tool_arguments):
    """
    Analyze how risky this Git operation is
    Returns: "low", "medium", "high"
    """
    
    # High risk: operations that could expose sensitive files
    if "file" in tool_name.lower():
        path = tool_arguments.get("path", "")
        sensitive_files = [".env", "secret", "password", "key", "token", "config"]
        if any(sensitive in path.lower() for sensitive in sensitive_files):
            return "high"
        return "medium"
    
    # Medium risk: operations that show code/history
    if tool_name in ["git_diff", "git_log", "git_search"]:
        return "medium"
    
    # Low risk: basic info operations
    return "low"

# =============================================================================
# ERROR MESSAGE FUNCTION
# =============================================================================
def create_git_block_message(request_id, operation, reason="Git operation blocked by security policy"):
    """
    Create an error message when we block a Git operation
    """
    error_response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32050,
            "message": "Git operation blocked by security policy",
            "data": {
                "reason": reason,
                "operation": operation,
                "suggestion": "This Git operation was flagged as potentially sensitive"
            }
        }
    }
    return json.dumps(error_response)

# =============================================================================
# MAIN LOOP: PROTECT GIT OPERATIONS
# =============================================================================
print("🛡️  Git security proxy is running. Protecting your repository...", file=sys.stderr)

for incoming_line in sys.stdin:
    incoming_line = incoming_line.strip()
    
    # Try to understand the request
    try:
        request = json.loads(incoming_line)
    except:
        # If it's not a proper request, just pass it through
        git_server.stdin.write(incoming_line + "\n")
        git_server.stdin.flush()
        continue
    
    # Handle batch requests (JSON arrays)
    is_batch = isinstance(request, list)
    
    # Check if this is a request that needs an answer
    is_real_request = isinstance(request, dict) and ("id" in request)
    
    # Check if someone wants to use a Git tool
    if is_real_request and request.get("method") == "tools/call":
        
        params = request.get("params", {})
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        # Analyze the risk level
        risk_level = analyze_git_risk(tool_name, tool_args)
        
        print(f"🔍 GIT SECURITY CHECK:", file=sys.stderr)
        print(f"   Operation: {tool_name}", file=sys.stderr)
        print(f"   Arguments: {tool_args}", file=sys.stderr)
        print(f"   Risk Level: {risk_level.upper()}", file=sys.stderr)
        
        # Ask security API if this is allowed
        decision = is_git_operation_allowed(tool_name, tool_args)
        
        if decision == "block":
            print(f"🚫 BLOCKED: {tool_name} (Risk: {risk_level})", file=sys.stderr)
            # Send detailed error message back to client
            error_msg = create_git_block_message(request["id"], tool_name)
            sys.stdout.write(error_msg + "\n")
            sys.stdout.flush()
            continue
        else:
            print(f"✅ ALLOWED: {tool_name} (Risk: {risk_level})", file=sys.stderr)
    
    # If we get here, the request is allowed
    # Send it to the Git MCP server
    git_server.stdin.write(incoming_line + "\n")
    git_server.stdin.flush()
    
    # If this was a real request OR batch, wait for the server's answer
    if is_real_request or is_batch:
        answer = git_server.stdout.readline()
        if answer:
            sys.stdout.write(answer)
            sys.stdout.flush()

# =============================================================================
# CLEANUP
# =============================================================================
print("🔄 Shutting down Git security proxy...", file=sys.stderr)
git_server.terminate()