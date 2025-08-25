#!/usr/bin/env python3
"""
OpenWebUI Terminal Runner
How to run OpenWebUI from terminal vs Docker
"""

import subprocess
import sys
import os

def explain_terminal_vs_docker():
    """Explain the differences between running OpenWebUI via terminal vs Docker"""
    print("🔍 OpenWebUI: Terminal vs Docker")
    print("=" * 50)
    
    print("\n📦 DOCKER METHOD:")
    print("   docker run -d -p 3000:8080 ghcr.io/open-webui/open-webui:main")
    print("   ✅ Isolated environment")
    print("   ✅ No dependency conflicts") 
    print("   ✅ Easy updates")
    print("   ❌ Requires Docker installed")
    print("   ❌ Less control over Python environment")
    
    print("\n💻 TERMINAL METHOD (What we're doing):")
    print("   pip install open-webui")
    print("   open-webui serve")
    print("   ✅ Direct Python control")
    print("   ✅ Easy debugging/modification")
    print("   ✅ Custom virtual environment")
    print("   ❌ Dependency management required")
    print("   ❌ Potential conflicts with system packages")

def show_terminal_commands():
    """Show how to run OpenWebUI from terminal"""
    print("\n🚀 TERMINAL COMMANDS:")
    print("=" * 50)
    
    print("\n1. Basic Usage:")
    print("   open-webui serve")
    print("   # Runs on http://localhost:8080")
    
    print("\n2. Custom Host/Port:")
    print("   open-webui serve --host 127.0.0.1 --port 3000")
    print("   # Runs on http://127.0.0.1:3000")
    
    print("\n3. Development Mode:")
    print("   open-webui dev")
    print("   # Runs with hot reload for development")
    
    print("\n4. Available Commands:")
    commands = {
        'serve': 'Start the production server',
        'dev': 'Start development server with hot reload',
        'main': 'Main entry point (same as serve)'
    }
    
    for cmd, desc in commands.items():
        print(f"   • {cmd}: {desc}")

def create_startup_script():
    """Create a startup script for OpenWebUI"""
    script_content = '''#!/bin/bash
# OpenWebUI Startup Script for rag_terminal

echo "🚀 Starting OpenWebUI from rag_terminal"
echo "📍 Working directory: $(pwd)"

# Activate virtual environment
source .venv/bin/activate

# Check if OpenWebUI is installed
if ! command -v open-webui &> /dev/null; then
    echo "❌ OpenWebUI not found in virtual environment"
    echo "💡 Installing OpenWebUI..."
    pip install open-webui
fi

# Show system info
echo "✅ Python: $(python --version)"
echo "✅ OpenWebUI: $(pip show open-webui | grep Version)"

# Start OpenWebUI
echo "🌐 Starting OpenWebUI server..."
echo "📱 Open your browser to: http://localhost:8080"
echo "🛑 Press Ctrl+C to stop"

open-webui serve --host 127.0.0.1 --port 8080
'''
    
    with open('start_openwebui.sh', 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod('start_openwebui.sh', 0o755)
    print("\n✅ Created start_openwebui.sh script")

def main():
    print("🎯 OpenWebUI Terminal Setup Guide")
    
    explain_terminal_vs_docker()
    show_terminal_commands()
    create_startup_script()
    
    print("\n🎮 QUICK START:")
    print("=" * 50)
    print("1. ./start_openwebui.sh")
    print("2. Open http://localhost:8080")
    print("3. Start uploading documents and asking questions!")
    
    print("\n🔧 ENVIRONMENT INFO:")
    print(f"   Python: {sys.version}")
    print(f"   Working Dir: {os.getcwd()}")
    print(f"   Virtual Env: {os.environ.get('VIRTUAL_ENV', 'Not activated')}")

if __name__ == "__main__":
    main()