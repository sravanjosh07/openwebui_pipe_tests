# How People Use RAG in OpenWebUI (2025)

## 🎯 What is OpenWebUI RAG?

OpenWebUI's RAG (Retrieval Augmented Generation) allows users to chat with their documents, websites, and knowledge bases. Instead of just talking to a basic LLM, users can:

1. **Upload documents** → System extracts and indexes content
2. **Ask questions** → System finds relevant info + generates contextualized answers
3. **Get citations** → See exactly where information came from

## 🔄 Typical User Workflow

### Step 1: Document Upload
```
User → Workspace → Knowledge → Upload Documents
- PDFs, Word docs, Excel, PowerPoint, CSVs, etc.
- System automatically processes and indexes
```

### Step 2: Query with Context
```
User types: #document_name What is the main conclusion?
- # prefix tells system to use specific document
- System retrieves relevant chunks
- LLM generates answer with context
```

### Step 3: Citations & References
```
OpenWebUI shows:
- Generated answer
- Source citations
- Relevant document excerpts
```

## 🏗️ Technical Architecture (What Happens Under the Hood)

### 1. Document Ingestion Pipeline
```python
# Located: /retrieval/loaders/main.py
Document Upload → File Type Detection → Appropriate Loader → Text Extraction → Clean Up
```

**Supported Formats:**
- **Text:** `.txt`, `.md`, `.csv`
- **Documents:** `.pdf`, `.docx`, `.xlsx`, `.pptx`  
- **Web:** `.html`, `.htm`
- **Code:** `.py`, `.js`, `.java`, `.cpp`, etc.

**Processing Engines:**
- **Default:** Built-in Langchain loaders
- **Tika:** Apache Tika server (complex docs)
- **Docling:** Advanced document understanding
- **Mistral OCR:** AI-powered PDF processing
- **External APIs:** Custom document processing

### 2. Vector Storage System
```python
# Located: /retrieval/vector/
VectorItem = {
    id: str,           # Unique document chunk ID
    text: str,         # Actual text content
    vector: List[float], # Embedding representation  
    metadata: dict     # Source, page, etc.
}
```

**Supported Vector Databases:**
- **ChromaDB** (default)
- **Qdrant**
- **Pinecone** 
- **Milvus**
- **Elasticsearch**
- **PostgreSQL + pgvector**

### 3. Retrieval & Search
```python
# Located: /retrieval/web/ and /retrieval/models/
Query → Embedding → Vector Search → Re-ranking → Top Results
```

**Search Features:**
- **Semantic Search:** Vector similarity
- **Hybrid Search:** BM25 + Vector search  
- **Re-ranking:** ColBERT, CrossEncoder
- **Web Integration:** Google, Bing, DuckDuckGo
- **Relevance Filtering:** Configurable thresholds

### 4. Response Generation
```
Retrieved Context + User Query + RAG Template → LLM → Response with Citations
```

## 🚀 How People Actually Use OpenWebUI RAG

### Common Use Cases:

1. **Research & Analysis**
   ```
   Upload: Research papers, reports, articles
   Query: "What are the main findings about X?"
   Result: Summarized insights with source citations
   ```

2. **Document Q&A**
   ```
   Upload: Company policies, manuals, contracts  
   Query: "What is the policy on remote work?"
   Result: Specific policy details with page references
   ```

3. **Code Documentation**
   ```
   Upload: Source code, documentation, README files
   Query: "How does the authentication system work?"
   Result: Code explanations with file/line references
   ```

4. **Meeting & Content Analysis**
   ```
   Upload: Meeting transcripts, presentations
   Query: "What were the key action items?"
   Result: Extracted action items with timestamps
   ```

## ⚙️ Configuration & Setup

### Basic Setup (Version 0.5.X):
1. **Create Knowledge Base:** Workspace → Knowledge → +
2. **Upload Documents:** Drag & drop or browse files
3. **Configure Model:** Workspace → Models → + (70B+ recommended)
4. **Adjust Context:** Increase to 8192+ tokens for better RAG performance

### Advanced Configuration:
```python
# Admin Panel → Settings → Documents
- RAG Template: Customize how context is injected
- Embedding Model: Choose quality vs speed
- Content Extraction: Configure robust processing
- Hybrid Search: Enable BM25 + re-ranking
- Citation Settings: Control reference formatting
```

## 🎛️ Debug Environment Features

Our debug setup shows:
- ✅ Document processing pipeline
- ✅ Vector storage mechanisms  
- ✅ Retrieval and search flow
- ✅ Multiple engine support
- ✅ Real-time step tracing

## 💡 Best Practices (2025)

1. **Model Selection:** Use 70B+ parameters for best RAG performance
2. **Context Length:** Set to 8192+ tokens (not default 2048)
3. **Embedding Quality:** Use high-quality models (all-MiniLM-L6-v2, OpenAI)
4. **Document Preparation:** Clean, well-structured documents work best
5. **Query Technique:** Use `#document_name` prefix for specific document queries
6. **Engine Choice:** Use external APIs (GPT-4, Claude) for production quality

## 🔍 What Makes OpenWebUI RAG Special

- **Zero Setup:** Works out of the box
- **Multi-Format:** Handles 20+ document types
- **Flexible Storage:** Multiple vector database options
- **Web Integration:** Can pull from internet sources
- **Citation System:** Always shows sources
- **Hybrid Search:** Combines semantic + keyword search
- **Extensible:** Plugin architecture for custom engines

This is how people actually use RAG in OpenWebUI - it's designed to be user-friendly while being technically sophisticated under the hood!