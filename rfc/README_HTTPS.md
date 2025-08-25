# MCP HTTPS Proxy

This extends the stdio MCP proxy to support **streamable HTTPS transport**. Instead of intercepting stdin/stdout, it creates an HTTP server that receives MCP JSON-RPC requests and forwards them to a real MCP server.

## Architecture

```
MCP Client → HTTP Proxy (port 8000) → Real MCP Server (port 8001)
             ↓ (security checks)
```

## Files

- `mcp_mitm_https.py` - HTTP proxy server (based on mcp_mitm_wo_aice.py)
- `math_server_http.py` - HTTP version of the math server  
- `test_https_proxy.py` - Test client to demonstrate the proxy
- `.env.example` - Configuration template

## Quick Start

1. **Copy environment config:**
```bash
cp .env.example .env
```

2. **Start the real MCP server (Terminal 1):**
```bash
source activate mcp
python math_server_http_v2.py
```
Should show: `Server will be available at: http://localhost:8001/mcp`

3. **Start the proxy (Terminal 2):**
```bash  
source activate mcp
python mcp_mitm_https.py
```
Should show: `Proxy listening on: http://localhost:8000/mcp`

4. **Test the proxy (Terminal 3):**
```bash
source activate mcp  
python test_https_proxy.py
```

## What It Does

**Same security policy as the stdio version:**
- ✅ Logs all MCP handshakes and method calls
- ✅ Blocks tool calls containing the string '9' (toy policy)
- ✅ Allows all other tool calls to pass through
- ✅ Returns JSON-RPC error responses for blocked calls

**Key differences from stdio version:**
- 🔄 **HTTP transport** instead of stdin/stdout
- 🔄 **Async/await** handling for concurrent requests
- 🔄 **aiohttp** for both server and client functionality
- 🔄 **Health check endpoint** at `/health`

## Usage with Real Agents

To use this proxy with CrewAI or other MCP clients:

```python
# Instead of:
server_params = StdioServerParameters(
    command="python", 
    args=["math_server.py"]
)

# Use:
server_params = {
    "url": "http://localhost:8000/mcp",
    "transport": "streamable-http"  
}
```

## Configuration

Edit `.env` to customize:

- `PROXY_HOST` - Proxy bind address (default: localhost)  
- `PROXY_PORT` - Proxy port (default: 8000)
- `UPSTREAM_MCP_URL` - Real MCP server URL (default: http://localhost:8001/mcp)

## Security Features

**Current (toy policy):**
- Blocks requests containing '9' anywhere in tool name or arguments
- Comprehensive request/response logging
- JSON-RPC error responses for blocked requests

**Future integration points:**
- Aiceberg API risk assessment (config already present)
- Server allowlisting and provenance checks
- Per-tool RBAC and human approval workflows
- Token brokering and secret management

## Testing the Security

The test client demonstrates:

1. **✅ Allowed call:** `add(2, 3)` - passes through normally
2. **🚫 Blocked call:** `add(9, 1)` - returns JSON-RPC error -32050

Check the proxy logs to see the security decisions in real-time.

## Next Steps

This HTTP proxy provides the foundation for:
- Integration with web-based MCP clients
- Load balancing across multiple MCP servers  
- Advanced security policies via HTTP middleware
- Web dashboard for monitoring and control