# Building a Content Monitoring System: From Keywords to ML

## System Overview

```
User Input → Content Pipeline → AI Model → Response Pipeline → User Output
     ↓             ↓              ↓              ↓              ↓
  "Hello"    →  Check Safety  →  OpenAI    →  Check Output  →  "Hi there!"
  "Kill X"   →     BLOCK      →    ---     →      ---       →   Warning
```

## What We Built

We created a content monitoring system for OpenWebUI that evolved through three stages. The idea was to filter both user questions and AI responses for safety.

```
Stage 1: Basic Filter → Stage 2: + OpenAI → Stage 3: + ML Monitoring
   (Keywords)            (Real AI)           (Aiceberg API)
```

## Understanding OpenWebUI Pipelines

OpenWebUI pipelines sit between users and AI models. They can check messages, block bad content, and log conversations.

```
Normal Flow:
User → OpenWebUI → AI Model → Response → User

With Pipeline:
User → OpenWebUI → [PIPELINE] → AI Model → [PIPELINE] → Response → User
                      ↓                        ↓
                 Input Check              Output Check
```

## Stage 1: Basic Keyword Filter

We started simple. Block any message with "kill" in it, return an echo for everything else.

```
Stage 1 Flow:
User Input → Check for "kill" → Decision → Response
    ↓            ↓                ↓         ↓
"Hello"    → No "kill"        → Pass     → "Echo: Hello"
"Kill X"   → Has "kill"       → Block    → Warning Message
```

This taught us how OpenWebUI pipelines work. The code was straightforward - just check if "kill" appears in the text. It worked but was too rigid. "Kill a process" got blocked even though it's a technical question.

## Stage 2: Adding OpenAI

We kept the same keyword filtering but replaced echo responses with real OpenAI responses. This made conversations actually useful instead of just bouncing text back.

```
Before: "Echo: Hello" 
After:  "Hello! How can I help you today?"
```

This stage required API key management and error handling, but the core logic stayed the same.

## Stage 3: ML-Powered Monitoring (AiceMonitor)

This is where it got interesting. We replaced simple keyword matching with Aiceberg's ML API and added output monitoring.

```
Complete Flow:
User Input → ML Check → OpenAI → ML Check → Response
    ↓           ↓          ↓         ↓          ↓
"Hello"   → Pass      → GPT-4o → Pass      → AI Response
          (Event ID: abc123)      (Event ID: abc123)
                      ↓
             Dashboard tracks complete conversation
```

## How the ML Monitoring Works

Two API calls to Aiceberg:

```
Step 1: Check user input
POST /eap/v0/event
{"profile_id": "...", "input": "user question"}
Returns: {"event_id": "abc123", "event_result": "passed"}

Step 2: Check AI output  
POST /eap/v0/event
{"profile_id": "...", "event_id": "abc123", "output": "AI response"}
Returns: {"event_result": "passed"}
```

The event_id links both calls so the dashboard shows complete conversations, not just isolated messages.

## Docker vs Terminal

We tried running this with terminal commands first but hit problems:
- Module import errors
- Service discovery issues 
- API endpoint mismatches

Docker solved everything immediately. Official images, automatic networking, volume mounting for easy updates.

```yaml
services:
  pipelines:
    image: ghcr.io/open-webui/pipelines:main
    volumes:
      - ./aicemonitor.py:/app/pipelines/
  
  open-webui:
    environment:
      - OPENAI_API_BASE_URLS=http://pipelines:9099
```

## Environment Variables Needed

```
OPENAI_API_KEY="sk-..."
API_TOKEN="Bearer eyJ..."  
EVENT_MONITORING_PROFILE_ID="01JZ..."
AICEBERG_API_URL="https://prod.api.aiceberg.ai/eap/v0/event"
```
