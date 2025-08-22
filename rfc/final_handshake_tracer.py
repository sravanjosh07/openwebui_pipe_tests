"""
Final Handshake Tracer - Shows exactly where CrewAI's adapter calls MCP initialize
"""
import os
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
import mcp

# Simple patch to show handshake
original_initialize = mcp.ClientSession.initialize

async def traced_initialize(self):
    print("=" * 60)
    print("🤝 MCP HANDSHAKE HAPPENING NOW!")
    print("📍 Location: mcp/client/session.py:137 - ClientSession.initialize()")
    print("📍 Called by: CrewAI MCPServerAdapter")
    print("📍 Call stack:")
    print("   MCPServerAdapter.__init__()")
    print("   └── MCPAdapt.__init__() & start()")  
    print("       └── _run_loop() in background thread")
    print("           └── mcptools() context manager")
    print("               └── ClientSession.initialize() ← YOU ARE HERE")
    print("📤 Sending initialize request to MCP server...")
    
    result = await original_initialize(self)
    
    print("📥 Server responded!")
    print(f"   Server: {result.serverInfo.name} v{result.serverInfo.version}")
    print("✅ MCP HANDSHAKE COMPLETED!")
    print("=" * 60)
    
    return result

mcp.ClientSession.initialize = traced_initialize

print("🎯 CREWAI MCP ADAPTER HANDSHAKE TRACER")
print("=" * 60)

server_params = StdioServerParameters(
    command="python",
    args=["/Users/sravanjosh/Documents/agents_mcp/openwebui-clean/rfc/math_server.py"],
    env={**os.environ},
)

print("🚀 Creating MCPServerAdapter...")
print("   This will trigger the MCP handshake internally...")

try:
    with MCPServerAdapter(server_params) as mcp_tools:
        print(f"\n✅ SUCCESS! Tools available: {[t.name for t in mcp_tools]}")
        print("\n📋 What CrewAI's adapter did:")
        print("   1. Created MCPAdapt instance")
        print("   2. Spawned background thread") 
        print("   3. Called mcptools() to establish MCP connection")
        print("   4. Called ClientSession.initialize() - THE HANDSHAKE")
        print("   5. Wrapped MCP tools as CrewAI BaseTool objects")
        print("   6. Made tools available to CrewAI agents")

except Exception as e:
    print(f"❌ Error: {e}")

print("\n🔚 TRACE COMPLETED")