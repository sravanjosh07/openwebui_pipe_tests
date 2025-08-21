#!/usr/bin/env python3
"""
SIMPLE MCP ADAPTER WITH HANDSHAKE DEBUGGING
===========================================

This shows you how to create your own MCP adapter and debug the handshake process.
You can use this pattern to understand how CrewAI, LlamaIndex, or other adapters work.
"""

import asyncio
import json
import subprocess
import logging
from typing import List, Dict, Any
from dataclasses import dataclass

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('MCP_ADAPTER_DEBUG')

@dataclass
class MCPTool:
    """Simple tool representation"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    
    def call(self, arguments: Dict[str, Any]) -> Any:
        """This would be implemented by the adapter"""
        pass

class SimpleMCPAdapter:
    """
    A simple MCP adapter that shows the handshake process.
    
    This demonstrates the pattern used by CrewAI, LlamaIndex, and other adapters.
    """
    
    def __init__(self, command: str, args: List[str]):
        self.command = command
        self.args = args
        self.process = None
        self.tools = []
        self.initialized = False
        
    def __enter__(self):
        """Context manager entry - this is where the handshake happens!"""
        logger.info("🚀 SimpleMCPAdapter: Starting connection...")
        
        # Step 1: Start the MCP server process
        logger.info("📡 Starting MCP server subprocess...")
        self.process = subprocess.Popen(
            [self.command] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        logger.info("✅ Server process started")
        
        # Step 2: Perform the handshake
        logger.info("🤝 Performing MCP handshake...")
        self._perform_handshake()
        
        # Step 3: Discover tools
        logger.info("🔧 Discovering tools...")
        self._discover_tools()
        
        logger.info(f"✅ Connection established! Found {len(self.tools)} tools")
        return self.tools
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup"""
        if self.process:
            logger.info("🔄 Shutting down MCP server...")
            self.process.terminate()
            self.process = None
    
    def _send_request(self, method: str, params: Dict = None, request_id: int = None) -> Dict:
        """Send a JSON-RPC request and get the response"""
        request = {
            "jsonrpc": "2.0",
            "method": method
        }
        
        if request_id is not None:
            request["id"] = request_id
            
        if params:
            request["params"] = params
        
        logger.debug(f"→ Sending: {json.dumps(request)}")
        
        # Send the request
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        
        # Get response (only for requests with ID)
        if request_id is not None:
            response_line = self.process.stdout.readline()
            if response_line:
                response = json.loads(response_line.strip())
                logger.debug(f"← Received: {json.dumps(response)}")
                return response
        
        return {}
    
    def _perform_handshake(self):
        """THE HANDSHAKE HAPPENS HERE! This is what MCPServerAdapter does internally."""
        logger.info("🤝 Step 1: Sending 'initialize' request...")
        
        # Step 1: Send initialize request
        init_response = self._send_request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "simple-mcp-adapter",
                    "version": "1.0.0"
                }
            },
            request_id=1
        )
        
        if "result" in init_response:
            server_info = init_response["result"]
            logger.info(f"✅ Server responded: {server_info.get('serverInfo', {}).get('name', 'Unknown')}")
            logger.info(f"📋 Server capabilities: {list(server_info.get('capabilities', {}).keys())}")
        
        # Step 2: Send initialized notification
        logger.info("🤝 Step 2: Sending 'initialized' notification...")
        self._send_request(method="notifications/initialized")
        
        logger.info("✅ Handshake complete!")
        self.initialized = True
    
    def _discover_tools(self):
        """Discover available tools - this happens after handshake"""
        logger.info("🔍 Calling 'tools/list' to discover tools...")
        
        tools_response = self._send_request(
            method="tools/list",
            request_id=2
        )
        
        if "result" in tools_response:
            tools_data = tools_response["result"].get("tools", [])
            
            for tool_data in tools_data:
                tool = MCPTool(
                    name=tool_data["name"],
                    description=tool_data["description"],
                    input_schema=tool_data.get("inputSchema", {})
                )
                self.tools.append(tool)
                logger.info(f"🔧 Found tool: {tool.name} - {tool.description}")
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool through the MCP connection"""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        logger.info(f"🎯 Calling tool: {tool_name} with {arguments}")
        
        response = self._send_request(
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": arguments
            },
            request_id=3
        )
        
        if "result" in response:
            result = response["result"]
            logger.info(f"✅ Tool result: {result}")
            return result
        elif "error" in response:
            error = response["error"]
            logger.error(f"❌ Tool error: {error}")
            raise RuntimeError(f"Tool call failed: {error}")


def main():
    """Demonstrate the MCP adapter handshake process"""
    print("🚀 SIMPLE MCP ADAPTER DEBUGGING")
    print("=" * 50)
    print("This shows you exactly how MCP adapters work internally.")
    print("Watch the logs to see the handshake process!\n")
    
    # Use our simple adapter - this mimics what CrewAI MCPServerAdapter does
    with SimpleMCPAdapter("python", ["math_server.py"]) as tools:
        print(f"\n🎉 SUCCESS! Connected and found {len(tools)} tools:")
        for tool in tools:
            print(f"   - {tool.name}: {tool.description}")
        
        print("\n🧪 Testing a tool call...")
        # To test tool calls, you'd need to create an adapter instance
        # and call the call_tool method (left as exercise)

if __name__ == "__main__":
    main()