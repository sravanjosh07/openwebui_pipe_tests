# 🚀 How to Run OpenWebUI from Terminal

This guide shows you how to run OpenWebUI directly from the terminal instead of using Docker.

## 📋 Prerequisites

- Python 3.8+ installed
- Terminal/Command line access
- Internet connection for package installation

## 🏗️ Initial Setup (One-time)

### 1. Create Project Directory
```bash
mkdir rag_terminal
cd rag_terminal
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install OpenWebUI
```bash
pip install open-webui
```

### 4. Verify Installation
```bash
open-webui --help
```

## 🎮 Running OpenWebUI

### Quick Start (Recommended)

Use our automated startup script:

```bash
# Make sure you're in the rag_terminal directory
./start_openwebui.sh
```

### Manual Start

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Start OpenWebUI
open-webui serve
```

### Custom Configuration

```bash
# Custom host and port
open-webui serve --host 127.0.0.1 --port 3000

# Development mode (with hot reload)
open-webui dev
```

## 🌐 Accessing OpenWebUI

1. **Open your browser**
2. **Navigate to:** http://localhost:8080 (or your custom port)
3. **Create account:** First user becomes admin
4. **Start using RAG!**

## 📁 Project Structure

```
rag_terminal/
├── .venv/                           # Virtual environment
├── start_openwebui.sh              # Startup script
├── debug_rag.py                    # RAG debugging tool
├── run_openwebui.py                # Setup guide
├── OPENWEBUI_RAG_EXPLAINED.md      # RAG explanation
├── HOW_TO_RUN_OPENWEBUI_TERMINAL.md # This guide
└── .webui_secret_key               # Auto-generated security key
```

## 🔧 Available Commands

| Command | Description |
|---------|-------------|
| `open-webui serve` | Start production server |
| `open-webui dev` | Start development server with hot reload |
| `open-webui --help` | Show all available options |

### Command Options

```bash
open-webui serve [OPTIONS]

Options:
  --host TEXT     Host to bind to [default: 0.0.0.0]
  --port INTEGER  Port to bind to [default: 8080]
  --help          Show help message
```

## 📚 Using RAG Features

### 1. Upload Documents
```
1. Go to Workspace → Knowledge
2. Click + to create Knowledge Base
3. Upload your documents (PDF, DOCX, CSV, etc.)
4. Wait for processing to complete
```

### 2. Chat with Documents
```
Type in chat: #document_name What is the main topic?
- Use # prefix to reference specific documents
- Get answers with automatic citations
- View source references
```

### 3. Supported File Types
- **Documents:** PDF, DOCX, XLSX, PPTX
- **Text:** TXT, MD, CSV, HTML
- **Code:** PY, JS, JAVA, CPP, etc.
- **Other:** RTF, ODT, MSG, EPUB

## 🛠️ Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Check what's using port 8080
lsof -i :8080

# Use different port
open-webui serve --port 3000
```

#### 2. Virtual Environment Not Activated
```bash
# You should see (.venv) in your prompt
source .venv/bin/activate
```

#### 3. OpenWebUI Not Found
```bash
# Reinstall in virtual environment
pip install --upgrade open-webui
```

#### 4. Database Issues
```bash
# Remove database and restart (loses data!)
rm -rf *.db
open-webui serve
```

### Process Management

#### Check if Running
```bash
ps aux | grep open-webui
```

#### Stop OpenWebUI
```bash
# Method 1: Ctrl+C in terminal
# Method 2: Kill process
kill <process_id>
```

#### Restart
```bash
# Stop current instance, then:
./start_openwebui.sh
```

## 🔍 Debugging & Development

### Debug RAG Pipeline
```bash
python debug_rag.py
```

### View Logs
OpenWebUI logs are displayed in the terminal where you started it.

### Configuration Files
- **Database:** SQLite files in project directory
- **Secret Key:** `.webui_secret_key`
- **Vector DB:** ChromaDB (default)

## ⚡ Performance Tips

### 1. Increase Context Length
- Go to Admin Settings → Models
- Set context length to 8192+ tokens
- Improves RAG performance significantly

### 2. Choose Better Models
- Use 70B+ parameter models for best RAG results
- Consider external APIs (GPT-4, Claude) for production

### 3. Optimize Embedding Model
- Admin Settings → Documents
- Change to high-quality embedding model
- Examples: all-MiniLM-L6-v2, OpenAI embeddings

## 📊 Comparison: Terminal vs Docker

| Feature | Terminal Method | Docker Method |
|---------|----------------|---------------|
| **Setup** | `pip install open-webui` | `docker run ...` |
| **Control** | ✅ Full Python access | ❌ Limited access |
| **Debugging** | ✅ Easy debugging | ❌ Harder to debug |
| **Updates** | `pip upgrade` | `docker pull` |
| **Isolation** | ❌ Shared environment | ✅ Isolated |
| **Dependencies** | ❌ Manual management | ✅ Auto-managed |
| **Performance** | ✅ Native speed | ❌ Container overhead |

## 🚨 Security Notes

- **CORS Warning:** Default setup allows all origins (development only)
- **Production:** Configure proper CORS settings
- **Secret Key:** Automatically generated and stored
- **Admin Access:** First user becomes admin

## 📞 Getting Help

### Resources
- **OpenWebUI Docs:** https://docs.openwebui.com/
- **GitHub:** https://github.com/open-webui/open-webui
- **Issues:** https://github.com/open-webui/open-webui/issues

### Debug Information
```bash
# Show version
pip show open-webui

# Show Python info
python --version

# Show environment
echo $VIRTUAL_ENV
```

## 🎯 Quick Reference

### Start OpenWebUI
```bash
cd rag_terminal
./start_openwebui.sh
# Open http://localhost:8080
```

### Stop OpenWebUI
```bash
# Press Ctrl+C in terminal
```

### Debug RAG
```bash
python debug_rag.py
```

### Upload & Query
```
1. Upload docs → Workspace → Knowledge
2. Chat with: #doc_name your question here
3. Get answers with citations
```

That's it! You now have OpenWebUI running from the terminal with full RAG capabilities! 🎉