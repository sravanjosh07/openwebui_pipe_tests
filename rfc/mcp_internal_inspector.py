#!/usr/bin/env python3
"""
MCP HANDSHAKE INTERNAL INSPECTOR
===============================

This script shows you EXACTLY how libraries like CrewAI wrap around MCP servers
and where the handshake happens in the source code. Perfect for understanding
how to build proxies around MCP servers.
"""

import asyncio
import json
import subprocess
import sys
import os
import logging
import inspect
import traceback
from typing import Any, Dict, List
from dotenv import load_dotenv

load_dotenv(override=True)

class MCPInternalInspector:
    """Deep inspect MCP library internals to understand proxy patterns"""
    
    def __init__(self):
        self.math_server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "math_server.py")
        
        # Set up logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('MCP_INTERNAL_DEBUG')
        
    def print_section(self, title: str):
        """Print a formatted section header"""
        print(f"\n{'='*80}")
        print(f"🔍 {title}")
        print(f"{'='*80}")
    
    def print_step(self, step: str, details: str = ""):
        """Print a step"""
        print(f"📡 {step}")
        if details:
            print(f"   {details}")
    
    def get_source_safe(self, obj, method_name: str):
        """Safely get source code of a method"""
        try:
            if hasattr(obj, method_name):
                method = getattr(obj, method_name)
                source = inspect.getsource(method)
                return source
            return f"Method {method_name} not found"
        except Exception as e:
            return f"Could not get source: {e}"
    
    def print_source_snippet(self, source: str, title: str, max_lines: int = 30):
        """Print a source code snippet"""
        print(f"📜 {title}:")
        lines = source.split('\n')
        for i, line in enumerate(lines[:max_lines]):
            print(f"   {i+1:3d}: {line}")
        if len(lines) > max_lines:
            print(f"   ... ({len(lines) - max_lines} more lines)")
    
    async def inspect_crewai_adapter_source(self):
        """Inspect the actual CrewAI MCPServerAdapter source code"""
        self.print_section("CREWAI MCPServerAdapter INTERNAL SOURCE CODE")
        
        try:
            from crewai_tools import MCPServerAdapter
            from mcp import StdioServerParameters
            
            # Get file location
            adapter_file = inspect.getfile(MCPServerAdapter)
            self.print_step(f"MCPServerAdapter location: {adapter_file}")
            
            # Get class definition
            self.print_step("Getting MCPServerAdapter class source...")
            adapter_source = self.get_source_safe(MCPServerAdapter, '__init__')
            self.print_source_snippet(adapter_source, "MCPServerAdapter.__init__")
            
            # Get the critical __enter__ method - this is where handshake happens
            enter_source = self.get_source_safe(MCPServerAdapter, '__enter__')
            self.print_source_snippet(enter_source, "MCPServerAdapter.__enter__ (HANDSHAKE ENTRY POINT)")
            
            # Get any connection/initialization methods
            for method_name in ['_connect', '_initialize', 'connect', 'initialize', '_setup_connection']:
                if hasattr(MCPServerAdapter, method_name):
                    method_source = self.get_source_safe(MCPServerAdapter, method_name)
                    self.print_source_snippet(method_source, f"MCPServerAdapter.{method_name}")
            
            # Now let's trace the actual execution
            self.print_step("TRACING ACTUAL EXECUTION...")
            
            server_params = StdioServerParameters(
                command="python",
                args=[self.math_server_path],
                env=os.environ.copy()
            )
            
            # Create adapter and inspect its attributes before entering
            adapter = MCPServerAdapter(server_params)
            self.print_step("Adapter created. Attributes before __enter__:")
            for attr in dir(adapter):
                if not attr.startswith('_'):
                    value = getattr(adapter, attr, 'N/A')
                    print(f"   {attr}: {type(value)} = {value}")
            
            # Enter the context manager and see what happens
            self.print_step("ENTERING CONTEXT MANAGER - HANDSHAKE STARTS HERE!")
            
            with adapter as tools:
                self.print_step("Context manager entered successfully!")
                self.print_step("Adapter attributes after __enter__:")
                for attr in dir(adapter):
                    if not attr.startswith('_'):
                        value = getattr(adapter, attr, 'N/A')
                        print(f"   {attr}: {type(value)} = {value}")
                
                self.print_step(f"Tools returned: {len(tools)} tools")
                if tools:
                    tool = tools[0]
                    self.print_step(f"First tool: {tool.name}")
                    
                    # Get tool source if possible
                    tool_source = self.get_source_safe(tool, '_run')
                    if 'not found' not in tool_source:
                        self.print_source_snippet(tool_source, f"Tool._run method")
                
                return True
                
        except Exception as e:
            self.print_step("❌ CrewAI adapter inspection failed")
            print(f"   Error: {e}")
            traceback.print_exc()
            return False
    
    async def inspect_mcp_client_source(self):
        """Inspect the standard MCP client source code"""
        self.print_section("STANDARD MCP CLIENT INTERNAL SOURCE CODE")
        
        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client
            
            # Get file locations
            session_file = inspect.getfile(ClientSession)
            stdio_file = inspect.getfile(stdio_client)
            
            self.print_step(f"ClientSession location: {session_file}")
            self.print_step(f"stdio_client location: {stdio_file}")
            
            # Get the critical initialize method - THE HANDSHAKE
            init_source = self.get_source_safe(ClientSession, 'initialize')
            self.print_source_snippet(init_source, "ClientSession.initialize (THE HANDSHAKE METHOD)")
            
            # Get other critical methods
            for method_name in ['__init__', '__aenter__', 'list_tools', 'call_tool', '_send_request']:
                method_source = self.get_source_safe(ClientSession, method_name)
                if 'not found' not in method_source:
                    self.print_source_snippet(method_source, f"ClientSession.{method_name}")
            
            # Get stdio_client source
            stdio_source = self.get_source_safe(sys.modules['mcp.client.stdio'], 'stdio_client')
            if 'not found' not in stdio_source:
                self.print_source_snippet(stdio_source, "stdio_client function")
            
            return True
            
        except Exception as e:
            self.print_step("❌ MCP client inspection failed")
            print(f"   Error: {e}")
            traceback.print_exc()
            return False
    
    async def show_proxy_implementation_pattern(self):
        """Show exactly how to implement a proxy that intercepts handshakes"""
        self.print_section("PROXY IMPLEMENTATION PATTERN FOR MCP HANDSHAKES")
        
        self.print_step("Creating proxy pattern based on MCP internals...")
        
        # Create a working example
        proxy_example = '''
import asyncio
import json
import subprocess
from typing import Optional, Dict, Any

class MCPHandshakeProxy:
    """
    A proxy that sits between MCP client and server, intercepting and 
    potentially modifying the handshake and all subsequent communication.
    
    This shows you EXACTLY where each step happens and how to control it.
    """
    
    def __init__(self, target_command: str, target_args: list):
        self.target_command = target_command
        self.target_args = target_args
        self.target_process: Optional[subprocess.Popen] = None
        self.client_capabilities: Optional[Dict] = None
        self.server_capabilities: Optional[Dict] = None
        self.handshake_complete = False
        
    async def start_target_server(self):
        """Start the actual MCP server we're proxying to"""
        self.target_process = subprocess.Popen(
            [self.target_command] + self.target_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        print(f"🎯 Started target server: {self.target_command} {' '.join(self.target_args)}")
    
    async def handle_initialize_request(self, request: Dict) -> Dict:
        """
        Handle the 'initialize' request - PHASE 1 of handshake
        This is where capability negotiation happens
        """
        print("🤝 PROXY: Handling 'initialize' request")
        
        # Store client capabilities
        self.client_capabilities = request.get("params", {}).get("capabilities", {})
        print(f"   📥 Client capabilities: {list(self.client_capabilities.keys())}")
        
        # Forward to target server (you can modify the request here)
        modified_request = request.copy()
        # Example: Add proxy capabilities
        modified_request["params"]["clientInfo"]["name"] = "mcp-proxy"
        
        response = await self._forward_request_to_server(modified_request)
        
        # Store server capabilities and potentially modify them
        if "result" in response:
            self.server_capabilities = response["result"].get("capabilities", {})
            print(f"   📤 Server capabilities: {list(self.server_capabilities.keys())}")
            
            # Example: Modify server capabilities before returning to client
            # response["result"]["capabilities"]["proxy"] = {"version": "1.0"}
        
        return response
    
    async def handle_initialized_notification(self, request: Dict) -> Dict:
        """
        Handle the 'notifications/initialized' - PHASE 2 of handshake
        This signals handshake completion
        """
        print("🤝 PROXY: Handling 'notifications/initialized'")
        self.handshake_complete = True
        
        # Forward to server
        response = await self._forward_request_to_server(request)
        print("   ✅ Handshake complete! Proxy is now ready for tool operations")
        
        return response
    
    async def handle_tools_list(self, request: Dict) -> Dict:
        """
        Handle 'tools/list' request - Tool discovery
        This is where you can filter/modify available tools
        """
        print("🔧 PROXY: Handling 'tools/list'")
        
        response = await self._forward_request_to_server(request)
        
        if "result" in response:
            tools = response["result"].get("tools", [])
            print(f"   📋 Server has {len(tools)} tools: {[t['name'] for t in tools]}")
            
            # Example: Filter tools or add custom tools
            # filtered_tools = [t for t in tools if t['name'] in ['add', 'subtract']]
            # response["result"]["tools"] = filtered_tools
            
            # Example: Add a custom proxy tool
            custom_tool = {
                "name": "proxy_status",
                "description": "Get proxy status information",
                "inputSchema": {"type": "object", "properties": {}}
            }
            response["result"]["tools"].append(custom_tool)
            print(f"   🔄 Modified to {len(response['result']['tools'])} tools")
        
        return response
    
    async def handle_tools_call(self, request: Dict) -> Dict:
        """
        Handle 'tools/call' request - Tool execution
        This is where you can intercept specific tool calls
        """
        tool_name = request.get("params", {}).get("name", "")
        tool_args = request.get("params", {}).get("arguments", {})
        
        print(f"🎯 PROXY: Handling 'tools/call' for '{tool_name}' with args {tool_args}")
        
        # Handle custom proxy tools
        if tool_name == "proxy_status":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "content": [{"type": "text", "text": f"Proxy active, target: {self.target_command}"}],
                    "isError": False
                }
            }
        
        # Forward to target server (you can modify arguments here)
        response = await self._forward_request_to_server(request)
        
        # You can modify the response here
        if "result" in response:
            print(f"   ✅ Tool '{tool_name}' executed successfully")
        elif "error" in response:
            print(f"   ❌ Tool '{tool_name}' failed: {response['error']}")
        
        return response
    
    async def handle_client_message(self, message: str) -> str:
        """
        Main message handler - routes messages based on method
        This is the entry point for all client requests
        """
        try:
            request = json.loads(message)
            method = request.get("method", "")
            
            print(f"📨 PROXY: Received {method} request")
            
            # Route based on method
            if method == "initialize":
                response = await self.handle_initialize_request(request)
            elif method == "notifications/initialized":
                response = await self.handle_initialized_notification(request)
            elif method == "tools/list":
                response = await self.handle_tools_list(request)
            elif method == "tools/call":
                response = await self.handle_tools_call(request)
            else:
                # Forward unknown methods as-is
                print(f"   🔄 Forwarding unknown method: {method}")
                response = await self._forward_request_to_server(request)
            
            return json.dumps(response)
            
        except Exception as e:
            print(f"❌ PROXY: Error handling message: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": request.get("id") if 'request' in locals() else None,
                "error": {"code": -32603, "message": f"Proxy error: {str(e)}"}
            }
            return json.dumps(error_response)
    
    async def _forward_request_to_server(self, request: Dict) -> Dict:
        """Forward a request to the target server and return the response"""
        if not self.target_process:
            raise RuntimeError("Target server not started")
        
        # Send request
        request_json = json.dumps(request)
        self.target_process.stdin.write(request_json + "\\n")
        self.target_process.stdin.flush()
        
        # Get response (only for requests with ID, not notifications)
        if "id" in request:
            response_line = self.target_process.stdout.readline()
            if response_line:
                return json.loads(response_line.strip())
        
        return {}
    
    async def shutdown(self):
        """Cleanup"""
        if self.target_process:
            self.target_process.terminate()
            self.target_process = None

# Example usage:
async def run_proxy_example():
    proxy = MCPHandshakeProxy("python", ["math_server.py"])
    await proxy.start_target_server()
    
    # Simulate client messages
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"roots": {"listChanged": True}},
            "clientInfo": {"name": "test-client", "version": "1.0"}
        }
    }
    
    response = await proxy.handle_client_message(json.dumps(init_msg))
    print(f"Response: {response}")
    
    await proxy.shutdown()
        '''
        
        print("📜 COMPLETE PROXY IMPLEMENTATION:")
        lines = proxy_example.split('\n')
        for i, line in enumerate(lines, 1):
            print(f"   {i:3d}: {line}")
        
        self.print_step("🔑 KEY INSIGHTS FOR YOUR PROXY:")
        print("   1. HANDSHAKE HAPPENS IN YOUR handle_initialize_request() method")
        print("   2. You can modify client capabilities before forwarding to server")
        print("   3. You can modify server capabilities before returning to client")
        print("   4. notifications/initialized signals handshake completion")
        print("   5. After handshake, you control all tool discovery and execution")
        print("   6. Your proxy becomes a 'man-in-the-middle' for all MCP communication")
        
        self.print_step("🎯 HANDSHAKE INTERCEPTION POINTS:")
        print("   • Client → Proxy → Server: modify outgoing requests")
        print("   • Server → Proxy → Client: modify incoming responses")
        print("   • Add/remove tools in tools/list response")
        print("   • Intercept specific tool calls in tools/call")
        print("   • Add authentication, logging, rate limiting, etc.")
        
        return True
    
    async def run_all_inspections(self):
        """Run all internal inspections"""
        print("🚀 MCP INTERNAL INSPECTION SESSION")
        print("=" * 80)
        print("This shows you the ACTUAL SOURCE CODE of how libraries wrap MCP servers")
        print("and exactly where handshakes happen for building proxies.\n")
        
        results = {}
        
        # Internal source code inspection
        results['mcp_client_source'] = await self.inspect_mcp_client_source()
        results['crewai_adapter_source'] = await self.inspect_crewai_adapter_source()
        results['proxy_pattern'] = await self.show_proxy_implementation_pattern()
        
        # Summary
        self.print_section("INTERNAL INSPECTION SUMMARY")
        for test, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"   {test.upper()}: {status}")
        
        self.print_section("🎯 WHAT YOU LEARNED FOR PROXY DEVELOPMENT")
        print("✅ Where handshakes happen in library source code")
        print("✅ How to intercept initialize/initialized messages")
        print("✅ How to modify capabilities during negotiation")
        print("✅ How to filter/add tools in discovery phase")
        print("✅ How to intercept and modify tool executions")
        print("✅ Complete proxy implementation pattern")

async def main():
    """Main entry point"""
    inspector = MCPInternalInspector()
    await inspector.run_all_inspections()

if __name__ == "__main__":
    asyncio.run(main())