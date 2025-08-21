#!/usr/bin/env python3
"""
DIRECT MCP INITIALIZATION TRACER
===============================
Simple, focused tracer to see exactly where MCP handshake happens.
"""

import sys
import json
import inspect
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

# Monkey patch the mcpadapt library directly
def trace_mcpadapt():
    try:
        import mcpadapt.core
        
        # Get the original __enter__ method
        original_enter = mcpadapt.core.MCPAdapt.__enter__
        
        def traced_enter(self):
            print("🔥 MCPADAPT.__enter__ CALLED - HANDSHAKE STARTING!", file=sys.stderr)
            
            # Show the source code
            try:
                source = inspect.getsource(original_enter)
                print("📜 MCPAdapt.__enter__ SOURCE:", file=sys.stderr)
                for i, line in enumerate(source.split('\n')[:30], 1):
                    print(f"   {i:3d}: {line}", file=sys.stderr)
            except:
                print("   (Could not get source)", file=sys.stderr)
            
            print("🔄 EXECUTING HANDSHAKE...", file=sys.stderr)
            result = original_enter(self)
            print("✅ HANDSHAKE COMPLETE!", file=sys.stderr)
            return result
        
        # Replace the method
        mcpadapt.core.MCPAdapt.__enter__ = traced_enter
        print("✅ mcpadapt tracing enabled", file=sys.stderr)
        
    except Exception as e:
        print(f"❌ Failed to trace mcpadapt: {e}", file=sys.stderr)

# Main execution
print("🚀 DIRECT MCP INITIALIZATION TRACER", file=sys.stderr)
print("=" * 50, file=sys.stderr)

# Enable tracing
trace_mcpadapt()

# Create the adapter
server_params = StdioServerParameters(
    command="python",
    args=["/Users/sravan/Documents/agents/MCP/RPC/math_server.py"],
    env={}
)

print("\n🔗 Creating MCPServerAdapter...", file=sys.stderr)

try:
    with MCPServerAdapter(server_params) as tools:
        print(f"✅ Success! Found {len(tools)} tools", file=sys.stderr)
        for tool in tools:
            print(f"   - {tool.name}", file=sys.stderr)
            
except Exception as e:
    print(f"❌ Error: {e}", file=sys.stderr)