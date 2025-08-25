"""
Test client for the MCP HTTPS Proxy

This demonstrates how to connect to the proxy and make MCP calls over HTTP.
"""

import asyncio
import aiohttp
import json

PROXY_URL = "http://localhost:8000/mcp"

async def make_mcp_request(session, method, params=None, request_id=1):
    """Make an MCP JSON-RPC request."""
    request_data = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method
    }
    if params:
        request_data["params"] = params
    
    print(f"📤 Sending: {method}")
    
    async with session.post(PROXY_URL, json=request_data) as response:
        if response.status == 200:
            result = await response.json()
            print(f"📥 Response: {json.dumps(result, indent=2)}")
            return result
        else:
            print(f"❌ Error: {response.status}")
            error_text = await response.text()
            print(f"Error details: {error_text}")
            return None

async def make_mcp_notification(session, method, params=None):
    """Make an MCP JSON-RPC notification (no response expected)."""
    request_data = {
        "jsonrpc": "2.0", 
        "method": method
    }
    if params:
        request_data["params"] = params
    
    print(f"📤 Notification: {method}")
    
    async with session.post(PROXY_URL, json=request_data) as response:
        if response.status == 200:
            print("📥 Notification sent successfully")
        else:
            print(f"❌ Notification error: {response.status}")

async def test_mcp_proxy():
    """Test the MCP proxy with a full handshake and tool calls."""
    
    print("🎯 Testing MCP HTTPS Proxy")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        
        # Step 1: Initialize
        print("\n🤝 Step 1: Initialize handshake")
        init_response = await make_mcp_request(
            session, 
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "sampling": None,
                    "elicitation": None,
                    "experimental": None,
                    "roots": None
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        )
        
        if not init_response or "error" in init_response:
            print("❌ Initialize failed")
            return
        
        # Step 2: Send initialized notification
        print("\n📢 Step 2: Send initialized notification")
        await make_mcp_notification(session, "notifications/initialized")
        
        # Step 3: List tools
        print("\n📋 Step 3: List available tools")
        tools_response = await make_mcp_request(session, "tools/list")
        
        if tools_response and "result" in tools_response:
            tools = tools_response["result"]["tools"]
            print(f"🛠️  Available tools: {[tool['name'] for tool in tools]}")
        
        # Step 4: Test allowed tool call
        print("\n✅ Step 4: Test allowed tool call (no '9')")
        call_response = await make_mcp_request(
            session,
            "tools/call",
            {
                "name": "add",
                "arguments": {"a": 2, "b": 3}
            }
        )
        
        # Step 5: Test blocked tool call  
        print("\n🚫 Step 5: Test blocked tool call (contains '9')")
        blocked_response = await make_mcp_request(
            session,
            "tools/call", 
            {
                "name": "add",
                "arguments": {"a": 9, "b": 1}  # Contains '9' - should be blocked
            }
        )
        
        print("\n🎉 Test completed!")

if __name__ == "__main__":
    print("Make sure to start the proxy and math server first:")
    print("1. Terminal 1: python math_server_http.py") 
    print("2. Terminal 2: python mcp_mitm_https.py")
    print("3. Terminal 3: python test_https_proxy.py")
    print()
    
    asyncio.run(test_mcp_proxy())