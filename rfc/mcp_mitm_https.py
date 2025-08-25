"""
MCP HTTPS Proxy — streamable HTTP transport version

This proxy does four things:
1) Starts an HTTP server to accept MCP client connections
2) Forwards requests to a real MCP server via HTTP
3) Logs the handshake and every method (calls & notifications)  
4) Checks tool calls against a tiny policy (allow/block)

Usage:
  python mcp_mitm_https.py
  
Then configure your MCP client to connect to:
  http://localhost:8000/mcp (this proxy)
  
The proxy forwards to the real server at:
  UPSTREAM_MCP_URL (environment variable)
"""

import os
import sys
import json
import asyncio
import aiohttp
from aiohttp import web, ClientSession
from dotenv import load_dotenv
import logging

load_dotenv()

# Configuration
PROXY_HOST = os.environ.get("PROXY_HOST", "localhost")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "8000"))
UPSTREAM_MCP_URL = os.environ.get("UPSTREAM_MCP_URL", "http://localhost:8001/mcp")

# These are kept for future API integration (not used in the toy policy below)
API_URL = os.environ.get("AICEBERG_API_URL", "https://test.api.aiceberg.ai/eap/v0/event")
API_TOKEN = os.environ.get("AICEBERG_API_TOKEN", "YOUR_API_KEY")
PROFILE_ID = os.environ.get("AICEBERG_PROFILE_ID", "xxxx")
TIMEOUT_SECONDS = float(os.environ.get("AICEBERG_TIMEOUT_SECS", "0.8"))
ALLOW_ON_ERROR = os.environ.get("AICEBERG_FAIL_OPEN", "0") == "1"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

def create_block_message(request_id, reason: str = "Request blocked by security policy") -> dict:
    """Return JSON-RPC error for a blocked request."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32050,
            "message": "Request blocked by security policy",
            "data": {"reason": reason},
        },
    }

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

class MCPHTTPProxy:
    def __init__(self):
        self.client_session = None
        
    async def start_client_session(self):
        """Initialize the HTTP client session for upstream requests."""
        if not self.client_session:
            self.client_session = ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={'Content-Type': 'application/json'}
            )
    
    async def close_client_session(self):
        """Close the HTTP client session."""
        if self.client_session:
            await self.client_session.close()
            self.client_session = None

    async def handle_mcp_request(self, request):
        """Handle incoming MCP requests from clients."""
        try:
            # Parse the JSON-RPC request
            request_data = await request.json()
            
            method = request_data.get("method")
            req_id = request_data.get("id")
            
            # Log the incoming request
            if is_call(request_data):
                logger.info(f"← client CALL {method} id={req_id}")
            elif is_notification(request_data):
                logger.info(f"← client NOTE {method} id=None")
            else:
                logger.info("← client (unknown frame)")
            
            # Handle initialize method
            if method == "initialize" and is_call(request_data):
                params = request_data.get("params", {})
                logger.info(f"initialize → {json.dumps(params)}")
            elif method == "notifications/initialized" and is_notification(request_data):
                logger.info("notifications/initialized received — client is ready")
            
            # Security check for tool calls
            if is_call(request_data) and method == "tools/call":
                params = request_data.get("params", {})
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                logger.info(f"🔍 Checking: {tool_name} {tool_args}")
                
                decision = is_operation_allowed(tool_name, tool_args)
                if decision == "block":
                    logger.info(f"BLOCKED: {tool_name}")
                    blocked_response = create_block_message(req_id)
                    return web.json_response(blocked_response)
                else:
                    logger.info(f"ALLOWED: {tool_name}")
            
            # Forward the request to the upstream MCP server
            await self.start_client_session()
            
            async with self.client_session.post(
                UPSTREAM_MCP_URL,
                json=request_data,
                headers={'Content-Type': 'application/json'}
            ) as upstream_response:
                
                if upstream_response.status != 200:
                    logger.error(f"Upstream server error: {upstream_response.status}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32603,
                            "message": f"Upstream server error: {upstream_response.status}"
                        }
                    }
                    return web.json_response(error_response)
                
                response_data = await upstream_response.json()
                
                # Log the upstream response
                if is_call(request_data):
                    status = "OK" if "result" in response_data else "ERR"
                    logger.info(f"→ server RESP {method} id={response_data.get('id')} {status}")
                    
                    # Special handling for initialize response
                    if method == "initialize":
                        try:
                            if "result" in response_data:
                                result = response_data["result"]
                                proto = result.get("protocolVersion")
                                caps = list(result.get("capabilities", {}).keys())
                                server_info = result.get("serverInfo") or {}
                                server_name = server_info.get("name")
                                server_version = server_info.get("version")
                                logger.info(f"initialize result ← protocol={proto} caps={caps} server={server_name} {server_version}")
                        except Exception as e:
                            logger.info(f"Could not parse initialize result: {e}")
                
                return web.json_response(response_data)
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }, status=400)
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return web.json_response({
                "jsonrpc": "2.0", 
                "id": request_data.get("id") if 'request_data' in locals() else None,
                "error": {"code": -32603, "message": "Internal error"}
            }, status=500)

    async def health_check(self, request):
        """Health check endpoint."""
        return web.json_response({"status": "healthy", "proxy": "mcp-https-mitm"})

async def create_app():
    """Create the aiohttp web application."""
    app = web.Application()
    proxy = MCPHTTPProxy()
    
    # Routes
    app.router.add_post('/mcp', proxy.handle_mcp_request)
    app.router.add_get('/health', proxy.health_check)
    
    # Cleanup handler
    async def cleanup_handler(app):
        await proxy.close_client_session()
    
    app.on_cleanup.append(cleanup_handler)
    return app

async def main():
    """Main entry point."""
    logger.info("🔧 Starting MCP HTTPS Proxy...")
    logger.info(f"📡 Proxy listening on: http://{PROXY_HOST}:{PROXY_PORT}/mcp")
    logger.info(f"🎯 Forwarding to upstream: {UPSTREAM_MCP_URL}")
    
    app = await create_app()
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, PROXY_HOST, PROXY_PORT)
    
    try:
        await site.start()
        logger.info("✅ MCP HTTPS Proxy started!")
        logger.info("🛡️ Security checking enabled (blocking requests with '9')")
        
        # Keep the server running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("🔚 Shutting down...")
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())