#!/usr/bin/env python3
"""
Simple RAG Monitor
Easy-to-use real-time RAG pipeline monitor for OpenWebUI
"""

import sys
import subprocess
import threading
import time
import re
from datetime import datetime

class SimpleRAGMonitor:
    """Simple real-time RAG monitor"""
    
    def __init__(self):
        self.rag_active = False
        self.query_start = None
        
    def monitor_openwebui_output(self, process):
        """Monitor OpenWebUI process output for RAG operations"""
        print("🔍 Monitoring OpenWebUI for RAG operations...")
        print("Make queries in your browser to see the pipeline!")
        print("="*60)
        
        while True:
            try:
                output = process.stdout.readline()
                if not output:
                    break
                    
                line = output.decode('utf-8').strip()
                self.analyze_log_line(line)
                
            except Exception as e:
                print(f"Monitor error: {e}")
                break
    
    def analyze_log_line(self, line):
        """Analyze log line for RAG indicators"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # RAG indicators
        patterns = {
            '🚀 QUERY START': [
                'POST /api/chat/completions',
                'POST /api/v1/chats/'
            ],
            '🧠 EMBEDDING': [
                'Batches:',
                'it/s'
            ],
            '🔍 VECTOR SEARCH': [
                'query_doc:result',
                'Retrieved.*chunks'
            ],
            '📚 DOCUMENT FOUND': [
                'rag_test_dataset.pdf',
                'file_id',
                'source.*pdf'
            ],
            '✅ QUERY COMPLETE': [
                'POST /api/chat/completed'
            ]
        }
        
        for stage, indicators in patterns.items():
            if any(indicator in line for indicator in indicators):
                if stage == '🚀 QUERY START':
                    self.query_start = time.time()
                    print(f"\n{timestamp} | {stage}")
                    print(f"   📝 {line}")
                    
                elif stage == '🧠 EMBEDDING':
                    if 'Batches:' in line:
                        print(f"{timestamp} | {stage}")
                        print(f"   📝 Converting query to vectors...")
                        
                elif stage == '🔍 VECTOR SEARCH':
                    if 'query_doc:result' in line:
                        print(f"{timestamp} | {stage}")
                        # Extract document IDs
                        doc_ids = re.findall(r"'([a-f0-9\-]{8})", line)
                        if doc_ids:
                            print(f"   📋 Found {len(doc_ids)} relevant chunks")
                            print(f"   🔑 First chunk ID: {doc_ids[0]}...")
                        
                elif stage == '📚 DOCUMENT FOUND':
                    print(f"{timestamp} | {stage}")
                    if 'rag_test_dataset.pdf' in line:
                        print(f"   📄 Source: rag_test_dataset.pdf")
                    print(f"   📝 {line[:100]}...")
                    
                elif stage == '✅ QUERY COMPLETE':
                    elapsed = time.time() - self.query_start if self.query_start else 0
                    print(f"{timestamp} | {stage}")
                    print(f"   ⏱️  Total time: {elapsed*1000:.0f}ms")
                    print("="*60)
                
                break

def run_openwebui_with_monitor():
    """Run OpenWebUI with RAG monitoring"""
    print("🚀 STARTING OPENWEBUI WITH RAG MONITORING")
    print("="*60)
    
    monitor = SimpleRAGMonitor()
    
    try:
        # Start OpenWebUI process
        print("Starting OpenWebUI server...")
        process = subprocess.Popen(
            ['open-webui', 'serve'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=False,
            bufsize=1
        )
        
        # Start monitoring in separate thread
        monitor_thread = threading.Thread(
            target=monitor.monitor_openwebui_output,
            args=(process,)
        )
        monitor_thread.daemon = True
        monitor_thread.start()
        
        print("✅ OpenWebUI started with RAG monitoring!")
        print("🌐 Open http://localhost:8080 in your browser")
        print("📝 Make queries to see RAG pipeline in action")
        print("🛑 Press Ctrl+C to stop")
        print()
        
        # Wait for process
        process.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping OpenWebUI and monitor...")
        if 'process' in locals():
            process.terminate()
    
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Try running manually:")
        print("   Terminal 1: open-webui serve")
        print("   Terminal 2: python simple_rag_monitor.py")

def manual_monitor_mode():
    """Manual monitoring mode for existing OpenWebUI instance"""
    print("📺 MANUAL RAG MONITORING MODE")
    print("="*60)
    print("Run this while OpenWebUI is active in another terminal")
    print("Copy and paste log lines to analyze RAG operations")
    print("Type 'quit' to exit")
    print()
    
    monitor = SimpleRAGMonitor()
    
    while True:
        try:
            line = input("OpenWebUI log line: ")
            if line.lower() in ['quit', 'exit', 'q']:
                break
            
            if line.strip():
                monitor.analyze_log_line(line)
                
        except KeyboardInterrupt:
            break
    
    print("👋 Monitoring stopped")

def main():
    """Main function"""
    print("🎯 SIMPLE RAG PIPELINE MONITOR")
    print("Real-time monitoring of OpenWebUI RAG operations")
    print()
    
    print("Choose monitoring mode:")
    print("1. Auto-start OpenWebUI with monitoring")
    print("2. Monitor existing OpenWebUI instance")
    print("3. Show monitoring guide")
    print()
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == "1":
        run_openwebui_with_monitor()
    elif choice == "2":
        manual_monitor_mode()
    elif choice == "3":
        show_monitoring_guide()
    else:
        print("Invalid choice. Try again.")
        main()

def show_monitoring_guide():
    """Show monitoring guide"""
    guide = """
🔍 RAG MONITORING GUIDE
========================

## What You'll See During RAG Operations:

🚀 QUERY START     - User submits query
🧠 EMBEDDING       - Query converted to vectors  
🔍 VECTOR SEARCH   - Search for similar documents
📚 DOCUMENT FOUND  - Relevant content retrieved
✅ QUERY COMPLETE  - Response generated with citations

## Log Patterns to Watch:

**Regular Query (No RAG):**
```
POST /api/chat/completions
POST /api/chat/completed
```

**RAG Query:**
```
POST /api/chat/completions
Batches: 100%|████| 1/1 [00:00<00:00, 2.58it/s]
query_doc:result [['doc-id-1', 'doc-id-2']]
POST /api/chat/completed
```

## Quick Test:

1. Start monitoring
2. Make regular query: "Hello"
3. Make RAG query: "#knowledge_base tell me about X"  
4. Compare the outputs!

## Tips:

- Upload a document first for RAG to work
- Use # prefix to explicitly trigger RAG
- Watch for "Batches:" and "query_doc:result" patterns
- Total RAG queries take longer (embeddings + search)
"""
    print(guide)

if __name__ == "__main__":
    main()