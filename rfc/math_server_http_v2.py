"""
HTTP MCP Server using raw MCP implementation

Since FastMCP doesn't support custom HTTP servers, we'll create a simple
HTTP wrapper around the MCP protocol.
"""

import asyncio
import json
from aiohttp import web
import mcp.types as types
from mcp.server import Server
import mcp.server.stdio

# Create MCP server instance
server = Server("math")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Return available math tools."""
    return [
        types.Tool(
            name="add",
            description="Add two numbers (ints or floats)",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        ),
        types.Tool(
            name="subtract", 
            description="Subtract b from a (ints or floats)",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        ),
        types.Tool(
            name="multiply",
            description="Multiply two numbers (ints or floats)", 
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        ),
        types.Tool(
            name="divide",
            description="Divide numerator by denominator (floats ok)",
            inputSchema={
                "type": "object", 
                "properties": {
                    "numerator": {"type": "number", "description": "Number to divide"},
                    "denominator": {"type": "number", "description": "Number to divide by"}
                },
                "required": ["numerator", "denominator"]
            }
        ),
        types.Tool(
            name="power",
            description="Raise base to the power of exponent (floats ok)",
            inputSchema={
                "type": "object",
                "properties": {
                    "base": {"type": "number", "description": "Base number"},
                    "exponent": {"type": "number", "description": "Exponent"}
                },
                "required": ["base", "exponent"]
            }
        ),
        types.Tool(
            name="sqrt", 
            description="Calculate the square root of a number",
            inputSchema={
                "type": "object",
                "properties": {
                    "number": {"type": "number", "description": "Number to find square root of"}
                },
                "required": ["number"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls."""
    
    if name == "add":
        result = arguments["a"] + arguments["b"]
    elif name == "subtract":
        result = arguments["a"] - arguments["b"] 
    elif name == "multiply":
        result = arguments["a"] * arguments["b"]
    elif name == "divide":
        if arguments["denominator"] == 0:
            raise ValueError("Cannot divide by zero")
        result = arguments["numerator"] / arguments["denominator"]
    elif name == "power":
        result = arguments["base"] ** arguments["exponent"]
    elif name == "sqrt":
        if arguments["number"] < 0:
            raise ValueError("Cannot calculate square root of a negative number")
        result = arguments["number"] ** 0.5
    else:
        raise ValueError(f"Unknown tool: {name}")
    
    return [types.TextContent(type="text", text=str(result))]

async def handle_mcp_request(request):
    """Handle incoming MCP JSON-RPC requests."""
    try:
        request_data = await request.json()
        
        # Handle different MCP methods
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")
        
        if method == "initialize":
            # Return server capabilities
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "logging": {},
                        "prompts": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False}
                    },
                    "serverInfo": {
                        "name": "math",
                        "version": "1.0.0"
                    }
                }
            }
            
        elif method == "tools/list":
            tools = await handle_list_tools()
            response = {
                "jsonrpc": "2.0", 
                "id": request_id,
                "result": {
                    "tools": [tool.model_dump() for tool in tools]
                }
            }
            
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            try:
                content = await handle_call_tool(tool_name, tool_args)
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id, 
                    "result": {
                        "content": [c.model_dump() for c in content]
                    }
                }
            except Exception as e:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }
                
        elif method == "notifications/initialized":
            # Notification - no response needed
            return web.Response(status=204)
            
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        
        return web.json_response(response)
        
    except json.JSONDecodeError:
        return web.json_response({
            "jsonrpc": "2.0", 
            "id": None,
            "error": {"code": -32700, "message": "Parse error"}
        }, status=400)
    except Exception as e:
        return web.json_response({
            "jsonrpc": "2.0",
            "id": request_data.get("id") if 'request_data' in locals() else None,
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
        }, status=500)

async def create_app():
    """Create the HTTP server app."""
    app = web.Application()
    app.router.add_post('/mcp', handle_mcp_request)
    app.router.add_get('/health', lambda r: web.json_response({"status": "healthy"}))
    return app

async def main():
    """Run the HTTP MCP server."""
    print("🧮 Starting Math MCP Server on HTTP...")
    print("📡 Server will be available at: http://localhost:8001/mcp")
    
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8001)
    
    try:
        await site.start()
        print("✅ Math MCP Server started!")
        
        # Keep the server running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("🔚 Shutting down...")
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())