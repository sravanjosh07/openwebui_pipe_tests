# pip/uv: crewai crewai-tools mcp
import os
import sys
import json
import logging
import traceback
import inspect
from crewai import Agent, Task, Crew
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

from dotenv import load_dotenv
load_dotenv()

# Set up detailed logging to see the MCP handshake
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler('mcp_debug.log')
    ]
)

# Get loggers for MCP components
mcp_logger = logging.getLogger('mcp')
crewai_logger = logging.getLogger('crewai_tools')

def debug_breakpoint(message: str, obj=None, method_name: str = None):
    """Debug breakpoint to trace execution and show source code"""
    print(f"\n🔴 DEBUG BREAKPOINT: {message}", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    
    # Show current call stack
    print("📚 CALL STACK:", file=sys.stderr)
    stack = traceback.format_stack()
    for i, frame in enumerate(stack[-6:]):  # Show last 6 frames
        print(f"   Frame {i}: {frame.strip()}", file=sys.stderr)
    
    if obj and method_name:
        try:
            if hasattr(obj, method_name):
                method = getattr(obj, method_name)
                source = inspect.getsource(method)
                print(f"\n📜 SOURCE CODE for {obj.__class__.__name__}.{method_name}:", file=sys.stderr)
                lines = source.split('\n')
                for i, line in enumerate(lines[:25], 1):  # Show first 25 lines
                    print(f"   {i:3d}: {line}", file=sys.stderr)
                if len(lines) > 25:
                    print(f"   ... ({len(lines) - 25} more lines)", file=sys.stderr)
            else:
                print(f"❌ Method {method_name} not found in {obj.__class__.__name__}", file=sys.stderr)
        except Exception as e:
            print(f"❌ Could not get source for {method_name}: {e}", file=sys.stderr)
    
    print("=" * 80, file=sys.stderr)

def monkey_patch_for_tracing(cls, method_names):
    """Monkey patch class methods to trace when they're called"""
    original_methods = {}
    
    for method_name in method_names:
        if hasattr(cls, method_name):
            original_method = getattr(cls, method_name)
            original_methods[method_name] = original_method
            
            def create_traced_method(orig_method, name):
                def traced_method(self, *args, **kwargs):
                    print(f"\n🎯 TRACED CALL: {self.__class__.__name__}.{name}", file=sys.stderr)
                    print(f"   Self: {self}", file=sys.stderr)
                    print(f"   Args: {args[:2] if len(args) > 2 else args}", file=sys.stderr)
                    print(f"   Kwargs keys: {list(kwargs.keys())}", file=sys.stderr)
                    
                    # Show source code of the method being called
                    try:
                        source = inspect.getsource(orig_method)
                        print(f"📜 EXECUTING METHOD ({name}):", file=sys.stderr)
                        lines = source.split('\n')
                        for i, line in enumerate(lines[:20], 1):
                            print(f"   {i:3d}: {line}", file=sys.stderr)
                        if len(lines) > 20:
                            print(f"   ... ({len(lines) - 20} more lines)", file=sys.stderr)
                    except Exception as e:
                        print(f"   (Could not get source for {name}: {e})", file=sys.stderr)
                    
                    print(f"🔄 EXECUTING {name}...", file=sys.stderr)
                    result = orig_method(self, *args, **kwargs)
                    print(f"✅ {name} COMPLETED. Result type: {type(result)}", file=sys.stderr)
                    return result
                return traced_method
            
            setattr(cls, method_name, create_traced_method(original_method, method_name))
    
    return original_methods

print("🚀 Starting MCP Connection Debug Session", file=sys.stderr)
print("=" * 60, file=sys.stderr)

server_params = StdioServerParameters(
    command="python",
    args=["/Users/sravan/Documents/agents/MCP/RPC/math_server.py"],
    env={**os.environ},
)

print(f"📡 Server Command: {server_params.command}", file=sys.stderr)
print(f"📡 Server Args: {server_params.args}", file=sys.stderr)

try:
    print("\n🔗 Setting up tracing for MCPServerAdapter...", file=sys.stderr)
    
    # 🔴 BREAKPOINT 1: Before any MCPServerAdapter operations
    debug_breakpoint("BEFORE setting up tracing")
    
    # Monkey patch MCPServerAdapter to trace all its methods
    methods_to_trace = [
        '__init__', '__enter__', '__exit__', 'start', 'stop', 
        'initialize', '_initialize', 'connect', '_connect', 
        '_setup_connection', 'tools'
    ]
    
    original_methods = monkey_patch_for_tracing(MCPServerAdapter, methods_to_trace)
    print("✅ Tracing setup complete!", file=sys.stderr)
    
    # 🔴 BREAKPOINT 2: About to create MCPServerAdapter
    debug_breakpoint("ABOUT TO CREATE MCPServerAdapter - __init__ will be traced")
    
    print("\n🔗 Creating MCPServerAdapter...", file=sys.stderr)
    
    # 🔴 THIS IS LINE 42 EQUIVALENT - Creating the adapter
    adapter = MCPServerAdapter(server_params, connect_timeout=60)
    
    # 🔴 BREAKPOINT 3: After creation, let's inspect the internal adapter
    debug_breakpoint("AFTER MCPServerAdapter creation - examining internal _adapter")
    print(f"📋 Internal _adapter: {adapter._adapter}", file=sys.stderr)
    print(f"📋 Internal _adapter type: {type(adapter._adapter)}", file=sys.stderr)
    
    # Let's trace the internal adapter's methods too if it exists
    if adapter._adapter:
        internal_methods_to_trace = ['__enter__', '__exit__', 'initialize', 'list_tools', 'call_tool']
        print("🔍 Setting up tracing for internal MCP adapter...", file=sys.stderr)
        for method_name in internal_methods_to_trace:
            if hasattr(adapter._adapter, method_name):
                original_method = getattr(adapter._adapter, method_name)
                
                def create_internal_traced_method(orig_method, name):
                    def traced_method(*args, **kwargs):
                        print(f"\n🎯 INTERNAL MCP CALL: {name}", file=sys.stderr)
                        print(f"   Args: {args[:2] if len(args) > 2 else args}", file=sys.stderr)
                        
                        try:
                            source = inspect.getsource(orig_method)
                            print(f"📜 INTERNAL METHOD SOURCE ({name}):", file=sys.stderr)
                            lines = source.split('\n')
                            for i, line in enumerate(lines[:15], 1):
                                print(f"   {i:3d}: {line}", file=sys.stderr)
                            if len(lines) > 15:
                                print(f"   ... ({len(lines) - 15} more lines)", file=sys.stderr)
                        except:
                            print(f"   (Could not get source for internal {name})", file=sys.stderr)
                        
                        print(f"🔄 EXECUTING INTERNAL {name}...", file=sys.stderr)
                        result = orig_method(*args, **kwargs)
                        print(f"✅ INTERNAL {name} COMPLETED. Result type: {type(result)}", file=sys.stderr)
                        return result
                    return traced_method
                
                setattr(adapter._adapter, method_name, create_internal_traced_method(original_method, method_name))
    
    with adapter as mcp_tools:
        
        # 🔴 BREAKPOINT 4: Inside context manager
        debug_breakpoint("INSIDE CONTEXT MANAGER - handshake should be complete")
        
        print(f"✅ Connection established!", file=sys.stderr)
        
        # Fix the tools access - need to call the tools method properly
        print(f"📋 Adapter tools property type: {type(adapter.tools)}", file=sys.stderr)
        
        # The tools property returns a method, so we need to check how to access it properly
        if hasattr(adapter, '_tools') and adapter._tools:
            tools_list = adapter._tools
            print(f"🔍 Tools discovered via _tools: {[t.name for t in tools_list]}", file=sys.stderr)
        else:
            print("❌ No tools found via _tools", file=sys.stderr)
            
        # Let's also inspect the internal MCPAdapt object to understand its structure
        if adapter._adapter:
            print(f"📋 Internal MCPAdapt object: {adapter._adapter}", file=sys.stderr)
            print(f"📋 Internal MCPAdapt attributes: {[attr for attr in dir(adapter._adapter) if not attr.startswith('_')]}", file=sys.stderr)
            
            # Try to get tools from the internal adapter
            if hasattr(adapter._adapter, 'tools'):
                try:
                    internal_tools = adapter._adapter.tools
                    print(f"📋 Internal adapter tools: {internal_tools}", file=sys.stderr)
                    print(f"📋 Internal adapter tools type: {type(internal_tools)}", file=sys.stderr)
                except Exception as e:
                    print(f"❌ Error accessing internal tools: {e}", file=sys.stderr)
        
        # Let's try to get tools using the tools() method if it exists
        try:
            if hasattr(adapter, 'tools') and callable(getattr(adapter, 'tools', None)):
                tools_list = adapter.tools()
                print(f"🔍 Tools discovered via tools(): {[t.name for t in tools_list]}", file=sys.stderr)
            elif adapter._tools:
                tools_list = adapter._tools
                print(f"🔍 Tools discovered via _tools: {[t.name for t in tools_list]}", file=sys.stderr)
            else:
                tools_list = []
                print("❌ No tools found", file=sys.stderr)
        except Exception as e:
            print(f"❌ Error getting tools: {e}", file=sys.stderr)
            tools_list = []
        
        # Show detailed tool information
        print("\n📋 Tool Details:", file=sys.stderr)
        for tool in tools_list:
            print(f"   - {tool.name}: {getattr(tool, 'description', 'No description')}", file=sys.stderr)
        
        # Let's also examine the first tool to see how it works
        if tools_list:
            first_tool = tools_list[0]
            debug_breakpoint(f"EXAMINING FIRST TOOL: {first_tool.name}", first_tool, '_run')
        
        agent = Agent(
            role="Math user",
            goal="Use MCP tools",
            backstory="A test agent that interacts with the math MCP server.",
            tools=tools_list,  # Use the proper tools list
            verbose=True,
            max_iter=3,
            max_retry_limit=0,
            allow_delegation=False,
        )
        
        task = Task(
            description="""add three and five.""",
            expected_output="The final numeric result of the calculation.",
            agent=agent
        )

        print("\n🎯 Starting task execution...", file=sys.stderr)
        result = Crew(agents=[agent], tasks=[task]).kickoff()
        print(f"\n✅ Task completed! Result: {result}", file=sys.stderr)

except Exception as e:
    print(f"❌ Error: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)