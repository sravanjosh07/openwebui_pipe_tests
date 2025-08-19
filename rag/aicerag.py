"""
AiceRAG Pipeline - RAG-Enhanced Content Filter + OpenAI
Preserves OpenWebUI's RAG context while monitoring both input and output
"""

import os
import json
import requests
import openai
from typing import List, Dict, Any, Union, Generator, Iterator
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class Pipeline:
    """
    AiceRAG content filtering pipeline
    Preserves OpenWebUI RAG functionality + Aiceberg monitoring
    """
    
    class Valves(BaseModel):
        """
        Configuration options for the pipeline
        """
        enabled: bool = Field(default=True, description="Enable AiceRAG content filtering")
        
        # Aiceberg ML API settings
        api_url: str = Field(
            default="",
            description="Aiceberg ML API endpoint (leave empty for env)"
        )
        api_token: str = Field(default="", description="API token (leave empty for env)")
        profile_id: str = Field(default="", description="Profile ID (leave empty for env)")
        
        # OpenAI settings
        openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model")
        openai_api_key: str = Field(default="", description="OpenAI key (leave empty for env)")
        
        # Response messages
        block_message: str = Field(
            default="🚫 This content violates Aiceberg policies and cannot be processed.",
            description="Message for blocked content"
        )
        flagged_message: str = Field(
            default="⚠️ This content has been flagged for review. Please rephrase your message.",
            description="Message for flagged content"
        )
    
    def __init__(self):
        """Initialize the pipeline"""
        self.name = "AiceRAG"
        self.valves = self.Valves()
        
        # Initialize OpenAI client
        openai_key = self.valves.openai_api_key or os.getenv("OPENAI_API_KEY")
        self.openai_client = openai.OpenAI(api_key=openai_key) if openai_key else None
        
        # Get ML API credentials
        self.api_token = self.valves.api_token or os.getenv("API_TOKEN", "")
        self.profile_id = self.valves.profile_id or os.getenv("EVENT_MONITORING_PROFILE_ID", "")
        self.api_url = self.valves.api_url or os.getenv("AICEBERG_API_URL", "")
        
        print(f"🤖 AiceRAG Pipeline initialized")
        print(f"   - AiceMonitor API: {'✅' if self.api_token and self.profile_id else '❌'}")
        print(f"   - OpenAI: {'✅' if self.openai_client else '❌'}")
    
    async def on_startup(self):
        """Called when the pipeline starts up"""
        print(f"🚀 AiceRAG Pipeline starting up")
    
    async def on_shutdown(self):
        """Called when the pipeline shuts down"""
        print("🛑 AiceRAG Pipeline shutting down")
    
    def check_input_with_aicemonitor(self, message: str, rag_context: str = None) -> dict:
        """
        Check input content using Aiceberg ML API
        Returns: {"signal": "none|block|modify", "result": "passed|rejected|flagged", "event_id": "..."}
        """
        if not self.api_token or not self.profile_id:
            print("⚠️ AiceMonitor API credentials missing - skipping input check")
            return {"signal": "none", "result": "passed", "event_id": None}
        
        try:
            headers = {
                "Authorization": self.api_token.strip(),
                "Content-Type": "application/json"
            }
            payload = {
                "profile_id": self.profile_id,
                "input": message
            }
            
            # Add RAG context if available
            if rag_context:
                payload["rag_context"] = rag_context
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.ok:
                data = response.json()
                signal = data.get("input_signal_result", "none")
                result = data.get("event_result", "passed")
                event_id = data.get("event_id")
                
                print(f"🔍 AiceRAG Input: signal={signal}, result={result}")
                return {"signal": signal, "result": result, "event_id": event_id}
            else:
                print(f"❌ AiceRAG Input API error: {response.status_code}")
                return {"signal": "none", "result": "passed", "event_id": None}
                
        except Exception as e:
            print(f"❌ AiceRAG Input API exception: {str(e)}")
            return {"signal": "none", "result": "passed", "event_id": None}
    
    def send_rag_content_as_prompt(self, rag_content: str) -> dict:
        """
        Send RAG content as a standalone prompt (like initial user input)
        NO event_id - behaves like a fresh prompt
        Returns: {"signal": "none|block|modify", "result": "passed|rejected|flagged"}
        """
        if not self.api_token or not self.profile_id or not rag_content:
            print("⚠️ AiceRAG API credentials or rag_content missing - skipping RAG content logging")
            return {"signal": "none", "result": "passed"}
        
        try:
            headers = {
                "Authorization": self.api_token.strip(),
                "Content-Type": "application/json"
            }
            
            # Send as a prompt (no event_id, just like initial user input)
            payload = {
                "profile_id": self.profile_id,
                "input": f"[RAG DOCUMENTS] {rag_content}",  # Mark it clearly as RAG content
                # NO event_id - this creates a new standalone entry
            }
            
            print(f"📄 Sending RAG as standalone prompt: content_length={len(rag_content)}")
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.ok:
                data = response.json()
                signal = data.get("input_signal_result", "none")
                result = data.get("event_result", "passed")
                new_event_id = data.get("event_id", "unknown")
                
                print(f"✅ RAG Prompt SUCCESS: signal={signal}, result={result}, new_event_id={new_event_id}")
                return {"signal": signal, "result": result, "event_id": new_event_id}
            else:
                print(f"❌ RAG Prompt API error: {response.status_code}")
                try:
                    error_details = response.json()
                    print(f"RAG error response: {error_details}")
                except:
                    print(f"Error text: {response.text}")
                return {"signal": "none", "result": "passed"}
                
        except Exception as e:
            print(f"❌ RAG Prompt API exception: {str(e)}")
            return {"signal": "none", "result": "passed"}

    def check_output_with_aicemonitor(self, message: str, event_id: str) -> dict:
        """
        Check output content using Aiceberg ML API with event_id
        Returns: {"signal": "none|block|modify", "result": "passed|rejected|flagged"}
        """
        if not self.api_token or not self.profile_id or not event_id:
            print("⚠️ AiceRAG API credentials or event_id missing - skipping output check")
            return {"signal": "none", "result": "passed"}
        
        try:
            headers = {
                "Authorization": self.api_token.strip(),
                "Content-Type": "application/json"
            }
            payload = {
                "profile_id": self.profile_id,
                "event_id": event_id,
                "output": message
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.ok:
                data = response.json()
                signal = data.get("output_signal_result", "none")
                result = data.get("event_result", "passed")
                
                print(f"🔍 AiceRAG Output: signal={signal}, result={result}")
                return {"signal": signal, "result": result}
            else:
                print(f"❌ AiceRAG Output API error: {response.status_code}")
                try:
                    error_details = response.json()
                    print(f"Error details: {error_details}")
                except:
                    print(f"Error text: {response.text}")
                return {"signal": "none", "result": "passed"}
                
        except Exception as e:
            print(f"❌ AiceRAG Output API exception: {str(e)}")
            return {"signal": "none", "result": "passed"}
    
    def get_rag_enhanced_response(self, messages: List[dict]) -> str:
        """
        Get response from OpenAI using the full RAG-enhanced message context
        This preserves OpenWebUI's RAG processing while adding monitoring
        """
        if not self.openai_client:
            return f"RAG Echo: {messages[-1].get('content', 'No message')}"
        
        try:
            # Use the full message history which includes RAG context from OpenWebUI
            print(f"📚 Processing {len(messages)} messages (including RAG context)")
            
            response = self.openai_client.chat.completions.create(
                model=self.valves.openai_model,
                messages=messages,  # This includes RAG context from OpenWebUI!
                temperature=0.7,
                max_tokens=1500  # Increased for RAG responses
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ OpenAI RAG error: {str(e)}")
            return "Sorry, I'm having trouble processing your RAG-enhanced request."
    
    def extract_user_message(self, messages: List[dict]) -> str:
        """Extract the original user message for monitoring (without RAG context)"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""
    
    def extract_rag_context(self, messages: List[dict]) -> str:
        """Extract ONLY the pure document content from RAG context"""
        rag_documents = ""
        
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                
                # Look for <source> tags which contain the actual documents
                if "<source" in content and "</source>" in content:
                    import re
                    # Extract content between <source> tags
                    source_pattern = r'<source[^>]*>(.*?)</source>'
                    sources = re.findall(source_pattern, content, re.DOTALL)
                    
                    for i, source in enumerate(sources, 1):
                        # Clean up the source content
                        clean_source = source.strip()
                        if clean_source and len(clean_source) > 20:  # Only meaningful content
                            rag_documents += f"Document {i}: {clean_source}\n\n"
        
        return rag_documents.strip()
    
    def is_suggestion_call(self, user_message: str, messages: List[dict], body: dict) -> bool:
        """Detect if this is an OpenWebUI suggestion/autocomplete call"""
        
        # Primary check: Look for ### Task: patterns (case insensitive)
        if "### task:" in user_message.lower():
            return True
            
        # Check common OpenWebUI background task patterns
        task_patterns = [
            "analyze the chat history",
            "suggest 3-5 relevant follow-up",
            "generate a concise",
            "generate 1-3 broad tags",
            "respond to the user query using",
            "### task:",
            "follow_up",
            "suggest", "complete", "autocomplete"
        ]
        
        for pattern in task_patterns:
            if pattern in user_message.lower():
                print(f"🔍 Detected suggestion pattern: {pattern}")
                return True
        
        # Check if it's a suggestion request in the body
        if "suggestion" in str(body).lower() or "autocomplete" in str(body).lower():
            return True
            
        # Check if it's a very short query with streaming (likely suggestion)
        if len(user_message.strip()) < 5 and body.get("stream", False):
            return True
            
        return False
    
    def pipe(
        self, 
        user_message: str, 
        model_id: str, 
        messages: List[dict], 
        body: dict
    ) -> Union[str, Generator, Iterator]:
        """
        Main RAG pipeline function - preserves OpenWebUI RAG + adds monitoring
        """
        print(f"🔄 AiceRAG Processing: {user_message[:50]}...")
        print(f"📚 Message context: {len(messages)} messages")
        
        # CHECK: Skip suggestion/autocomplete calls
        if self.is_suggestion_call(user_message, messages, body):
            print(f"⏭️ Skipping suggestion call - processing without monitoring")
            return self.get_rag_enhanced_response(messages)
        
        # Extract the original user query and RAG context
        original_user_message = self.extract_user_message(messages)
        rag_context = self.extract_rag_context(messages)
        
        if rag_context:
            print(f"📄 RAG Context detected: {len(rag_context)} chars")
        
        # Step 1: Monitor the original user input (without RAG context in input call)
        input_result = self.check_input_with_aicemonitor(original_user_message)
        signal = input_result["signal"]
        result = input_result["result"]
        event_id = input_result["event_id"]
        
        # Handle blocked content
        if result == "rejected" or signal == "block":
            print(f"🚫 Content BLOCKED by AiceRAG: {original_user_message[:30]}...")
            return self.valves.block_message
        
        # Step 1.5: Send RAG content as standalone prompt (no event_id)
        if rag_context:
            print(f"📄 Logging RAG content as standalone prompt...")
            rag_result = self.send_rag_content_as_prompt(rag_context)
            
            if rag_result["result"] == "passed":
                print(f"✅ RAG content logged as standalone prompt with new event_id: {rag_result.get('event_id', 'unknown')}")
            else:
                print(f"⚠️ RAG prompt logging had issues: {rag_result}")
        
        # Process with OpenAI (including RAG context)
        print(f"✅ Input APPROVED by AiceRAG - processing with RAG context")
        
        # Get RAG-enhanced response from OpenAI
        ai_response = self.get_rag_enhanced_response(messages)
        
        # Step 2: Monitor the AI output
        if event_id:
            try:
                output_result = self.check_output_with_aicemonitor(ai_response, event_id)
                output_signal = output_result["signal"]
                output_result_status = output_result["result"]
                
                # Handle problematic outputs
                if output_result_status == "rejected" or output_signal == "block":
                    print(f"🚫 RAG Output BLOCKED by AiceRAG: {ai_response[:30]}...")
                    return "⚠️ The RAG-enhanced response was flagged by our content monitoring system."
                    
                elif output_result_status == "flagged" or output_signal == "modify":
                    print(f"⚠️ RAG Output FLAGGED by AiceRAG: {ai_response[:30]}...")
                    return "⚠️ The RAG-enhanced response requires review. Please try rephrasing your question."
                
                else:
                    print(f"✅ RAG Output APPROVED by AiceRAG")
                    
            except Exception as e:
                print(f"⚠️ RAG output monitoring failed but continuing: {str(e)}")
        else:
            print(f"⚠️ No event_id available - skipping RAG output monitoring")
        
        return ai_response