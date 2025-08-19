# RAG - Document Q&A with Monitoring

RAG implementation that monitors user queries, document content, and AI responses separately.

## What it does
Upload PDFs to OpenWebUI, ask questions about them, and see everything logged in your monitoring dashboard.

## Files
- `aicerag.py` - RAG pipeline with monitoring
- `docker-compose.yml` - setup

## How to use
```bash
cd rag
docker-compose up -d
```

Note: The .env file is copied to this folder so it can access your API keys.

1. Go to http://localhost:8080
2. Upload a PDF in the Documents section
3. Ask questions using # before your query
4. Check your Aiceberg dashboard - you'll see separate entries for:
   - Your question
   - The document content
   - The AI response

Each conversation gets tracked with full audit trail.