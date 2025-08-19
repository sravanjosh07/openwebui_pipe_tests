# User2LLM - Basic Monitoring

Simple monitoring setup for OpenWebUI with Aiceberg backend.

## What's here
- `aicemonitor.py` - monitors user inputs and LLM outputs
- `basic_pipe.py` - basic pipeline 
- `basic_pipe_with_oai.py` - OpenAI version
- `docker-compose.yml` - runs everything

## Run it
```bash
cd user2llm
docker-compose up -d
```

OpenWebUI will be at http://localhost:8080

Make sure your .env file is in the parent directory with your API keys.