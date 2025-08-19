# OpenWebUI Monitoring Experiments

Different approaches to monitoring LLM conversations with OpenWebUI.

## Projects

### user2llm/
Basic monitoring setup. Tracks user inputs and AI responses.

### rag/  
RAG (document Q&A) with full monitoring. Upload PDFs, ask questions, see everything logged separately.

## Setup

Each folder has its own docker-compose setup. Put your .env file in this root directory.

```bash
# For basic monitoring
cd user2llm && docker-compose up -d

# For RAG monitoring  
cd rag && docker-compose up -d
```

Both run OpenWebUI on http://localhost:8080

## Environment

Need these in your .env file:
```bash
OPENAI_API_KEY="sk-..."
API_TOKEN="Bearer eyJ..."  
EVENT_MONITORING_PROFILE_ID="01JZ..."
AICEBERG_API_URL="https://prod.api.aiceberg.ai/eap/v0/event"
WEBUI_SECRET_KEY="some-random-string"
```