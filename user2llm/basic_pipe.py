"""
Basic OpenWebUI Pipeline - Toxicity Checker
A simple pipeline that filters messages for toxic content
"""

from typing import List, Dict, Any, Union, Generator, Iterator
from pydantic import BaseModel, Field


def check_word(text_to_check: str) -> bool:
    """Return True if 'kill' appears (case-insensitive)."""
    return "kill" in (text_to_check or "").lower()


class Pipeline:
    """
    Basic toxicity checking pipeline for OpenWebUI
    Filters messages and blocks toxic content
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
    
    def __init__(self):
        """Initialize the pipeline with default valve settings"""
        self.name = "Toxicity Checker"
        self.valves = self.Valves()
    
    async def on_startup(self):
        """Called when the pipeline starts up"""
        print(f"Toxicity Checker Pipeline starting up")
    
    async def on_shutdown(self):
        """Called when the pipeline shuts down"""
        print("Toxicity Checker Pipeline shutting down")
    
    def pipe(
        self, 
        user_message: str, 
        model_id: str, 
        messages: List[dict], 
        body: dict
    ) -> Union[str, Generator, Iterator]:
        """
        Main pipeline function - check for toxicity and block if found
        """
        print(f"Toxicity Checker: Checking current message: {user_message[:50]}...")
        
        # Only check the current user message for toxic content
        if check_word(user_message):
            print(f"🚫 Toxic content detected: {user_message[:50]}...")
            return self.valves.block_message
        
        print("✅ Message passed toxicity check - processing normally")
        
        # If no toxic content found, pass through to the actual model
        # This is a simple echo response - in a real setup you'd forward to an LLM
        return f"Echo: {user_message}"