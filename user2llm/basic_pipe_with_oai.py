"""
Enhanced OpenWebUI Pipeline - Toxicity Checker with OpenAI Integration
Filters toxic content and forwards clean messages to OpenAI GPT-4o-mini
"""

import os
import openai
from typing import List, Dict, Any, Union, Generator, Iterator
from pydantic import BaseModel, Field


def check_word(text_to_check: str) -> bool:
    """Return True if 'kill' appears (case-insensitive)."""
    return "kill" in (text_to_check or "").lower()


class Pipeline:
    """
    Enhanced toxicity checking pipeline with OpenAI integration
    Filters messages and forwards clean content to GPT-4o-mini
    """
    
    class Valves(BaseModel):
        """
        Configuration options for the pipeline
        """
        enabled: bool = Field(default=True, description="Enable toxicity checking")
        block_message: str = Field(
            default="Sorry, I cannot process messages containing potentially harmful content.",
            description="Message to show when toxic content is detected"
        )
        openai_model: str = Field(
            default="gpt-4o-mini",
            description="OpenAI model to use for clean messages"
        )
        openai_api_key: str = Field(
            default="",
            description="OpenAI API key (leave empty to use environment variable)"
        )
    
    def __init__(self):
        """Initialize the pipeline with default valve settings"""
        self.name = "Toxicity Checker + GPT-4o-mini"
        self.valves = self.Valves()
        
        # Initialize OpenAI client
        api_key = self.valves.openai_api_key or os.getenv("OPENAI_API_KEY")
        if api_key:
            self.client = openai.OpenAI(api_key=api_key)
        else:
            self.client = None
            print("⚠️ Warning: No OpenAI API key found")
    
    async def on_startup(self):
        """Called when the pipeline starts up"""
        print(f"Enhanced Toxicity Checker + OpenAI Pipeline starting up")
    
    async def on_shutdown(self):
        """Called when the pipeline shuts down"""
        print("Enhanced Toxicity Checker + OpenAI Pipeline shutting down")
    
    def pipe(
        self, 
        user_message: str, 
        model_id: str, 
        messages: List[dict], 
        body: dict
    ) -> Union[str, Generator, Iterator]:
        """
        Main pipeline function - check for toxicity and forward to OpenAI if clean
        """
        print(f"Toxicity Checker: Checking current message: {user_message[:50]}...")
        
        # Only check the current user message for toxic content
        if check_word(user_message):
            print(f"🚫 Toxic content detected: {user_message[:50]}...")
            return self.valves.block_message
        
        print("✅ Message passed toxicity check - forwarding to OpenAI")
        
        # If no OpenAI client available, fall back to echo
        if not self.client:
            print("⚠️ No OpenAI client - falling back to echo")
            return f"Echo: {user_message}"
        
        try:
            # Forward clean message to OpenAI GPT-4o-mini
            response = self.client.chat.completions.create(
                model=self.valves.openai_model,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            ai_response = response.choices[0].message.content
            print(f"✅ OpenAI response received: {ai_response[:50]}...")
            return ai_response
            
        except Exception as e:
            print(f"❌ OpenAI API error: {str(e)}")
            return f"Sorry, I'm having trouble connecting to the AI service. Please try again later."