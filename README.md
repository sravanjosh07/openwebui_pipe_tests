# OpenWebUI Content Monitoring Pipeline

A content monitoring system for OpenWebUI using ML-powered analysis via Aiceberg API.

## Quick Start

1. Copy `.env.example` to `.env` and add your API keys
2. Start with Docker: `docker-compose up -d`
3. Access OpenWebUI at http://localhost:8080
4. Select "AiceMonitor" model to use the monitoring pipeline

## What It Does

- **Input Monitoring**: Checks user questions for safety using ML
- **Output Monitoring**: Checks AI responses for safety using ML  
- **Complete Tracking**: Links input/output pairs in dashboard
- **Context Aware**: Understands "kill process" vs harmful content

## Three Pipeline Evolution

**Stage 1: `basic_pipe.py`** - Simple keyword filtering (blocks "kill")  
**Stage 2: `basic_pipe_with_oai.py`** - Adds real OpenAI responses  
**Stage 3: `aicemonitor.py`** - ML-powered monitoring with complete conversation tracking  

Each stage builds on the previous one, making it easy to understand the progression.

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
OPENAI_API_KEY="sk-..."
API_TOKEN="Bearer eyJ..."  
EVENT_MONITORING_PROFILE_ID="01JZ..."
AICEBERG_API_URL="https://prod.api.aiceberg.ai/eap/v0/event"
WEBUI_SECRET_KEY="generate-random-string"
```

## Files

- `basic_pipe.py` - Stage 1: Simple keyword filter
- `basic_pipe_with_oai.py` - Stage 2: Keyword filter + OpenAI responses
- `aicemonitor.py` - Stage 3: ML-powered monitoring pipeline
- `docker-compose.yml` - Docker setup for easy deployment
- `ARTICLE.md` - Technical explanation and lessons learned

## Usage

All three pipelines will be available in OpenWebUI. You can switch between them to see the evolution:

- **"Toxicity Checker"** - Basic keyword blocking
- **"Toxicity Checker + GPT-4o-mini"** - Enhanced with real AI  
- **"AiceMonitor"** - Full ML monitoring system