"""
AiceMonitor Pipeline - ML-Powered Content Filter + OpenAI
Uses Aiceberg ML API for sophisticated content detection and OpenAI for responses
"""

import os
import json
import requests
import openai
from typing import List, Dict, Any, Union, Generator, Iterator
from pydantic import BaseModel, Field


class Pipeline:
    """
    AiceMonitor content filtering pipeline
    Uses Aiceberg ML API for detection + OpenAI for responses
    """
    
    class Valves(BaseModel):
        """
        Configuration options for the pipeline
        """
        enabled: bool = Field(default=True, description="Enable AiceMonitor content filtering")
        
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
        self.name = "AiceMonitor"
        self.valves = self.Valves()
        
        # Initialize OpenAI client
        openai_key = self.valves.openai_api_key or os.getenv("OPENAI_API_KEY")
        self.openai_client = openai.OpenAI(api_key=openai_key) if openai_key else None
        
        # Get ML API credentials
        self.api_token = self.valves.api_token or os.getenv("API_TOKEN", "")
        self.profile_id = self.valves.profile_id or os.getenv("EVENT_MONITORING_PROFILE_ID", "")
        self.api_url = self.valves.api_url or os.getenv("AICEBERG_API_URL", "")
        
        print(f"🤖 AiceMonitor Pipeline initialized")
        print(f"   - AiceMonitor API: {'✅' if self.api_token and self.profile_id else '❌'}")
        print(f"   - OpenAI: {'✅' if self.openai_client else '❌'}")
    
    async def on_startup(self):
        """Called when the pipeline starts up"""
        print(f"🚀 AiceMonitor Pipeline starting up")
    
    async def on_shutdown(self):
        """Called when the pipeline shuts down"""
        print("🛑 AiceMonitor Pipeline shutting down")
    
    def check_input_with_aicemonitor(self, message: str) -> dict:
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
                
                print(f"🔍 AiceMonitor Input: signal={signal}, result={result}")
                return {"signal": signal, "result": result, "event_id": event_id}
            else:
                print(f"❌ AiceMonitor Input API error: {response.status_code}")
                return {"signal": "none", "result": "passed", "event_id": None}
                
        except Exception as e:
            print(f"❌ AiceMonitor Input API exception: {str(e)}")
            return {"signal": "none", "result": "passed", "event_id": None}
    
    def check_output_with_aicemonitor(self, message: str, event_id: str) -> dict:
        """
        Check output content using Aiceberg ML API with event_id
        Returns: {"signal": "none|block|modify", "result": "passed|rejected|flagged"}
        """
        if not self.api_token or not self.profile_id or not event_id:
            print("⚠️ AiceMonitor API credentials or event_id missing - skipping output check")
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
                
                print(f"🔍 AiceMonitor Output: signal={signal}, result={result}")
                return {"signal": signal, "result": result}
            else:
                print(f"❌ AiceMonitor Output API error: {response.status_code}")
                try:
                    error_details = response.json()
                    print(f"Error details: {error_details}")
                except:
                    print(f"Error text: {response.text}")
                return {"signal": "none", "result": "passed"}
                
        except Exception as e:
            print(f"❌ AiceMonitor Output API exception: {str(e)}")
            return {"signal": "none", "result": "passed"}
    
    def get_openai_response(self, message: str) -> str:
        """Get response from OpenAI"""
        if not self.openai_client:
            return f"Echo: {message}"
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.valves.openai_model,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ OpenAI error: {str(e)}")
            return "Sorry, I'm having trouble connecting to the AI service."
    
    def pipe(
        self, 
        user_message: str, 
        model_id: str, 
        messages: List[dict], 
        body: dict
    ) -> Union[str, Generator, Iterator]:
        """
        Main pipeline function - ML content check + OpenAI response
        """
        # Skip OpenWebUI background tasks (they start with "### Task:")
        if user_message.startswith("### Task:"):
            print(f"⏭️ Skipping OpenWebUI background task")
            return self.get_openai_response(user_message)
        
        print(f"🔄 Processing user message: {user_message[:50]}...")
        
        # Step 1: Check input with AiceMonitor API and get event_id
        input_result = self.check_input_with_aicemonitor(user_message)
        signal = input_result["signal"]
        result = input_result["result"]
        event_id = input_result["event_id"]
        
        # Handle different AiceMonitor input results
        if result == "rejected" or signal == "block":
            print(f"🚫 Content BLOCKED by AiceMonitor: {user_message[:30]}...")
            return self.valves.block_message
            
        # elif result == "flagged" or signal == "modify":
        #     print(f"⚠️ Content FLAGGED by AiceMonitor: {user_message[:30]}...")
        #     return self.valves.flagged_message
            
        else:  # passed or none
            print(f"✅ Input APPROVED by AiceMonitor - forwarding to OpenAI")
            
            # Get OpenAI response
            ai_response = self.get_openai_response(user_message)
            
            # Step 2: Monitor the AI output with the same event_id (async, don't block response)
            if event_id:  # Only if we have a valid event_id
                try:
                    output_result = self.check_output_with_aicemonitor(ai_response, event_id)
                    output_signal = output_result["signal"]
                    output_result_status = output_result["result"]
                    
                    # Only block if output is truly problematic
                    if output_result_status == "rejected" or output_signal == "block":
                        print(f"🚫 AI Output BLOCKED by AiceMonitor: {ai_response[:30]}...")
                        return "⚠️ The AI response was flagged by our content monitoring system. Please try rephrasing your question."
                        
                    elif output_result_status == "flagged" or output_signal == "modify":
                        print(f"⚠️ AI Output FLAGGED by AiceMonitor: {ai_response[:30]}...")
                        return "⚠️ The AI response requires review. Please try a different approach to your question."
                    
                    else:
                        print(f"✅ Output APPROVED by AiceMonitor")
                        
                except Exception as e:
                    print(f"⚠️ Output monitoring failed but continuing: {str(e)}")
            else:
                print(f"⚠️ No event_id available - skipping output monitoring")
            
            return ai_response