# OpenWebUI Monitoring Experiments

Two different approaches to monitoring LLM conversations with OpenWebUI and Aiceberg backend.

## Projects

### user2llm/
Basic monitoring pipeline with three levels:
- **basic_pipe.py** - Simple keyword filtering  
- **basic_pipe_with_oai.py** - Keyword filtering + OpenAI responses
- **aicemonitor.py** - Full ML-powered monitoring with Aiceberg API

### rag/  
RAG (Retrieval Augmented Generation) with document Q&A monitoring:
- **aicerag.py** - Upload PDFs, ask questions, see everything logged separately
- Documents, user queries, and AI responses tracked independently

## Quick Start

**Note**: Only one can run at a time due to container name conflicts.

```bash
# Basic monitoring (3 pipeline evolution)
cd user2llm && docker-compose up -d

# RAG monitoring (document Q&A)  
cd rag && docker-compose up -d

# To switch: stop current, start other
docker-compose down && cd ../other-folder && docker-compose up -d
```

Both run OpenWebUI on http://localhost:8080

## Files

- `ARTICLE.md` - Technical deep dive and lessons learned
- `.env` / `.env.example` - Environment configuration  
- Each subfolder has its own README with specific instructions

## Environment Setup

Copy `.env.example` to each subfolder as `.env` and configure:
```bash
OPENAI_API_KEY="sk-..."
API_TOKEN="Bearer eyJ..."  
EVENT_MONITORING_PROFILE_ID="01J..."
AICEBERG_API_URL="https://prod..."
WEBUI_SECRET_KEY="some-random-string"
```