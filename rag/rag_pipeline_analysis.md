# RAG Pipeline Detailed Analysis

## How the RAG Pipeline Works

### Architecture Overview
```
User Upload PDF → OpenWebUI RAG System → Pipeline Monitoring → OpenAI → Response
                      ↓                       ↓                 ↓
                  Chunks & Embeds      Extract & Monitor    Monitor Output
```

### Step-by-Step Processing

#### 1. **Message Context Extraction**
When a user asks a question about uploaded documents, OpenWebUI sends the pipeline a `messages` array containing:

```python
messages = [
    {
        "role": "system", 
        "content": "Use the following context: <source>Document content here</source>"
    },
    {
        "role": "user", 
        "content": "What is the main topic?"
    }
]
```

#### 2. **RAG Context Extraction** 
```python
def extract_rag_context(self, messages: List[dict]) -> str:
    # Looks for <source> tags in system messages
    # Extracts actual document content
    # Returns clean document text
```

#### 3. **User Query Extraction**
```python
def extract_user_message(self, messages: List[dict]) -> str:
    # Finds the latest user message
    # Returns just the user's question (without RAG context)
```

#### 4. **Dual Monitoring Approach**
The pipeline monitors TWO things separately:

**A. User Query Monitoring:**
```python
input_result = self.check_input_with_aicemonitor(original_user_message)
# Sends: "What is the main topic?" 
# Gets back: event_id for tracking
```

**B. RAG Content Monitoring:**
```python
rag_result = self.send_rag_content_as_prompt(rag_context)
# Sends: "[RAG DOCUMENTS] Document content here..."
# Creates separate monitoring entry (no event_id linkage)
```

#### 5. **AI Processing**
```python
ai_response = self.get_rag_enhanced_response(messages)
# Sends full message context (including RAG) to OpenAI
# OpenAI generates response using both user query + document context
```

#### 6. **Output Monitoring**
```python
output_result = self.check_output_with_aicemonitor(ai_response, event_id)
# Links AI response back to original user query via event_id
```

### Key Features

#### A. **Suggestion Call Detection**
```python
def is_suggestion_call(self, user_message: str, messages: List[dict], body: dict) -> bool:
    # Detects OpenWebUI background operations
    # Skips monitoring for autocomplete/suggestions
    # Patterns: "### Task:", "suggest 3-5 relevant", etc.
```

#### B. **Three-Tier Monitoring**
1. **User Questions** - monitored with event tracking
2. **Document Content** - monitored as standalone prompts  
3. **AI Responses** - monitored and linked to user questions

#### C. **OpenWebUI Integration**
- Uses OpenWebUI's existing RAG infrastructure
- No custom document processing needed
- Leverages OpenWebUI's embedding and retrieval system

### Data Flow Example

**User uploads "company_policy.pdf" and asks: "What is the vacation policy?"**

1. **OpenWebUI** processes the PDF, creates embeddings, retrieves relevant chunks
2. **Pipeline receives:**
   ```
   messages = [
     {"role": "system", "content": "Context: <source>Vacation policy: 15 days annually...</source>"},
     {"role": "user", "content": "What is the vacation policy?"}
   ]
   ```
3. **Pipeline extracts:**
   - User query: "What is the vacation policy?"
   - RAG context: "Vacation policy: 15 days annually..."
4. **Monitoring calls:**
   - Monitor user query → gets event_id_123
   - Monitor RAG content → creates separate entry  
5. **OpenAI processing:**
   - Sends full context to GPT-4o-mini
   - Gets enhanced response using document content
6. **Output monitoring:**
   - Monitor AI response → links to event_id_123

### Benefits of This Approach

1. **Complete Audit Trail:** Every component is tracked separately
2. **Content Filtering:** Can block inappropriate documents or responses  
3. **RAG Enhancement:** Preserves OpenWebUI's RAG capabilities
4. **Compliance:** Detailed logging for regulatory requirements
5. **Flexibility:** Can modify or filter content at any stage

### Technical Implementation Notes

- **No Custom RAG:** Relies entirely on OpenWebUI's RAG system
- **Regex Parsing:** Uses regex to extract `<source>` tags from system messages
- **Event Linking:** Uses event_id to connect user queries with AI responses
- **Error Handling:** Graceful fallback when monitoring APIs fail
- **Environment Config:** All API credentials via environment variables

This architecture allows organizations to add sophisticated content monitoring to their existing OpenWebUI RAG workflows without rebuilding the retrieval system.