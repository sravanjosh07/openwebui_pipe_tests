#!/usr/bin/env python3
"""
MCP HANDSHAKE DEBUGGER
======================

This script shows you EXACTLY what happens during the MCP connection handshake
with MCPServerAdapter and other adapters. It intercepts the JSON-RPC messages
to show you the initialization flow.
"""

import asyncio
import json
import subprocess
import sys
import os
import logging
from typing import Any, Dict, List
from dotenv import load_dotenv

load_dotenv(override=True)

class MCPHandshakeDebugger:
    """Debug the MCP handshake process step by step"""
    
    def __init__(self):
        self.math_server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "math_server.py")
        
        # Set up logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('MCP_DEBUG')
        
    def print_section(self, title: str):
        """Print a formatted section header"""
        print(f"\n{'='*80}")
        print(f"🔍 {title}")
        print(f"{'='*80}")
    
    def print_step(self, step: str, details: str = ""):
        """Print a handshake step"""
        print(f"📡 {step}")
        if details:
            print(f"   {details}")
    
    def print_json_message(self, direction: str, message: dict):
        """Pretty print JSON-RPC messages"""
        arrow = "→" if direction == "send" else "←"
        msg_type = "REQUEST" if message.get("id") is not None and "method" in message else "RESPONSE" if "id" in message else "NOTIFICATION"
        
        print(f"   {arrow} {msg_type}: {json.dumps(message, indent=2)}")
    
    async def debug_raw_handshake(self):
        """Show the raw MCP handshake process step by step"""
        self.print_section("RAW MCP HANDSHAKE DEBUGGING")
        
        try:
            self.print_step("Starting MCP server process...")
            process = subprocess.Popen(
                ["python", self.math_server_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            self.print_step("Waiting for server startup...")
            await asyncio.sleep(1)
            
            # Step 1: Initialize request
            self.print_step("STEP 1: Sending 'initialize' request")
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {
                            "listChanged": True
                        },
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "debug-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            self.print_json_message("send", init_request)
            process.stdin.write(json.dumps(init_request) + "\n")
            process.stdin.flush()
            
            # Get initialize response
            response_line = process.stdout.readline()
            if response_line:
                init_response = json.loads(response_line.strip())
                self.print_step("STEP 1 RESPONSE: Server capabilities received")
                self.print_json_message("receive", init_response)
                
                # Parse server capabilities
                if "result" in init_response:
                    result = init_response["result"]
                    print(f"   🎯 Protocol Version: {result.get('protocolVersion')}")
                    print(f"   🛠️  Server Capabilities: {list(result.get('capabilities', {}).keys())}")
                    server_info = result.get('serverInfo', {})
                    print(f"   🏷️  Server Name: {server_info.get('name')}")
                    print(f"   📦 Server Version: {server_info.get('version')}")
            
            # Step 2: Send initialized notification
            self.print_step("STEP 2: Sending 'initialized' notification")
            initialized_notif = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            
            self.print_json_message("send", initialized_notif)
            process.stdin.write(json.dumps(initialized_notif) + "\n")
            process.stdin.flush()
            
            self.print_step("STEP 2 COMPLETE: Handshake finished - client is ready!")
            
            # Step 3: Discover tools
            self.print_step("STEP 3: Discovering available tools with 'tools/list'")
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            
            self.print_json_message("send", tools_request)
            process.stdin.write(json.dumps(tools_request) + "\n")
            process.stdin.flush()
            
            response_line = process.stdout.readline()
            if response_line:
                tools_response = json.loads(response_line.strip())
                self.print_step("STEP 3 RESPONSE: Tools discovered")
                self.print_json_message("receive", tools_response)
                
                if "result" in tools_response:
                    tools = tools_response["result"].get("tools", [])
                    print(f"   🔧 Found {len(tools)} tools:")
                    for tool in tools:
                        print(f"      - {tool['name']}: {tool.get('description', 'No description')}")
            
            # Step 4: Test tool call
            self.print_step("STEP 4: Testing tool call with 'tools/call'")
            call_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "add",
                    "arguments": {"a": 3, "b": 5}
                }
            }
            
            self.print_json_message("send", call_request)
            process.stdin.write(json.dumps(call_request) + "\n")
            process.stdin.flush()
            
            response_line = process.stdout.readline()
            if response_line:
                call_response = json.loads(response_line.strip())
                self.print_step("STEP 4 RESPONSE: Tool execution result")
                self.print_json_message("receive", call_response)
                
                if "result" in call_response:
                    content = call_response["result"].get("content", [])
                    print(f"   ✅ Tool result: {content}")
            
            # Cleanup
            process.terminate()
            
            self.print_step("🎉 HANDSHAKE COMPLETE!")
            print("   The MCP handshake consists of:")
            print("   1. Client sends 'initialize' request with capabilities")
            print("   2. Server responds with its capabilities")
            print("   3. Client sends 'initialized' notification")
            print("   4. Connection is ready for tool discovery and calls")
            
            return True
            
        except Exception as e:
            self.print_step("❌ Raw handshake failed")
            print(f"   Error: {e}")
            if 'process' in locals():
                process.terminate()
            return False
    
    async def debug_crewai_adapter_handshake(self):
        """Debug CrewAI MCPServerAdapter handshake"""
        self.print_section("CREWAI MCPServerAdapter HANDSHAKE DEBUGGING")
        
        try:
            self.print_step("Importing CrewAI MCP libraries...")
            from crewai_tools import MCPServerAdapter
            from mcp import StdioServerParameters
            
            self.print_step("Creating StdioServerParameters...")
            server_params = StdioServerParameters(
                command="python",
                args=[self.math_server_path],
                env=os.environ.copy()
            )
            
            self.print_step("Creating MCPServerAdapter (this triggers the handshake)...")
            print("   📡 MCPServerAdapter will now:")
            print("   1. Start the server process")
            print("   2. Send 'initialize' request")
            print("   3. Wait for server response")
            print("   4. Send 'initialized' notification")
            print("   5. Call 'tools/list' to discover tools")
            print("   6. Wrap tools for CrewAI usage")
            
            with MCPServerAdapter(server_params) as tools:
                self.print_step("✅ MCPServerAdapter connection established!")
                self.print_step("Handshake completed automatically by the adapter")
                
                print(f"   🔧 Tools available: {[tool.name for tool in tools]}")
                
                self.print_step("Testing tool access through adapter...")
                # The adapter has already done the handshake and tool discovery
                for tool in tools:
                    print(f"   - {tool.name}: {getattr(tool, 'description', 'No description')}")
                
                return True
                
        except ImportError as e:
            self.print_step("❌ CrewAI tools not available")
            print(f"   Error: {e}")
            return False
        except Exception as e:
            self.print_step("❌ CrewAI adapter handshake debug failed")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def debug_standard_mcp_client_handshake(self):
        """Debug standard MCP client handshake"""
        self.print_section("STANDARD MCP CLIENT HANDSHAKE DEBUGGING")
        
        try:
            self.print_step("Importing MCP client libraries...")
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            
            self.print_step("Creating server parameters...")
            server_params = StdioServerParameters(
                command="python",
                args=[self.math_server_path]
            )
            
            self.print_step("Starting stdio connection (this begins the handshake)...")
            async with stdio_client(server_params) as (read, write):
                self.print_step("Creating ClientSession...")
                async with ClientSession(read, write) as session:
                    self.print_step("Calling session.initialize() - THE HANDSHAKE HAPPENS HERE!")
                    print("   📡 session.initialize() does:")
                    print("   1. Sends 'initialize' request with client capabilities")
                    print("   2. Waits for server response with server capabilities")
                    print("   3. Sends 'initialized' notification")
                    print("   4. Handshake is complete!")
                    
                    # This is where the actual handshake happens
                    await session.initialize()
                    
                    self.print_step("✅ Session initialized - handshake complete!")
                    
                    self.print_step("Now we can use the session...")
                    tools_result = await session.list_tools()
                    print(f"   🔧 Tools: {[tool.name for tool in tools_result.tools]}")
                    
                    # Test a tool call
                    result = await session.call_tool("add", {"a": 3, "b": 5})
                    print(f"   ✅ Tool call result: {result.content}")
                    
                    return True
                    
        except ImportError as e:
            self.print_step("❌ MCP client libraries not available")
            print(f"   Error: {e}")
            return False
        except Exception as e:
            self.print_step("❌ Standard MCP client handshake debug failed")
            print(f"   Error: {e}")
            return False
    
    async def run_all_handshake_debugging(self):
        """Run all handshake debugging tests"""
        print("🚀 MCP HANDSHAKE DEBUGGING SESSION")
        print("=" * 80)
        print("This will show you EXACTLY where and how the 'initialize' method is called")
        print("during MCP connections with different adapters.\n")
        
        results = {}
        
        # Test 1: Raw handshake to understand the protocol
        results['raw_handshake'] = await self.debug_raw_handshake()
        
        # Test 2: Standard MCP client handshake
        results['mcp_client_handshake'] = await self.debug_standard_mcp_client_handshake()
        
        # Test 3: CrewAI adapter handshake
        results['crewai_adapter_handshake'] = await self.debug_crewai_adapter_handshake()
        
        # Summary
        self.print_section("HANDSHAKE DEBUGGING SUMMARY")
        for test, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"   {test.upper()}: {status}")
        
        self.print_section("KEY DEBUGGING INSIGHTS")
        print("🔍 WHERE THE 'INITIALIZE' METHOD IS CALLED:")
        print("   1. RAW PROTOCOL: You manually send the 'initialize' JSON-RPC request")
        print("   2. MCP CLIENT: session.initialize() handles the handshake")
        print("   3. CREWAI ADAPTER: MCPServerAdapter.__enter__() does it automatically")
        print("   4. OTHER ADAPTERS: Usually in their connection/setup methods")
        
        print("\n🛠️  DEBUGGING THE HANDSHAKE:")
        print("   - Set MCP logging to DEBUG level")
        print("   - Use stdio transport with bufsize=1 for real-time debugging")
        print("   - Monitor stdin/stdout for JSON-RPC messages")
        print("   - Check server stderr for initialization errors")
        print("   - Verify protocol version compatibility")
        
        print("\n📋 HANDSHAKE FLOW:")
        print("   Client → initialize(capabilities) → Server")
        print("   Client ← initialize_result(server_capabilities) ← Server")
        print("   Client → initialized() notification → Server")
        print("   🎉 Connection ready for tools/list and tools/call")

async def main():
    """Main entry point"""
    debugger = MCPHandshakeDebugger()
    await debugger.run_all_handshake_debugging()

if __name__ == "__main__":
    asyncio.run(main())