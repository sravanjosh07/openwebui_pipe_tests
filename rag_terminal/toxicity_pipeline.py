"""
OpenWebUI Toxicity Pipeline - Kill Word Checker
A simple pipeline that filters messages for toxic content using OpenWebUI's native pipeline system

This is the CORRECT way to filter prompts in OpenWebUI!
"""

from typing import List, Dict, Any, Union, Generator, Iterator
from pydantic import BaseModel, Field
import re


class Pipeline:
    """
    Toxicity checking pipeline for OpenWebUI
    Filters messages and blocks toxic content before reaching the model
    """
    
    class Valves(BaseModel):
        """
        Configuration options for the pipeline
        These can be adjusted from OpenWebUI admin interface
        """
        enabled: bool = Field(
            default=True, 
            description="Enable toxicity checking"
        )
        
        block_message: str = Field(
            default="Sorry, I cannot process messages containing potentially harmful content.",
            description="Message to show when toxic content is detected"
        )
        
        kill_words: str = Field(
            default="kill,hack,exploit,harmful,dangerous,illegal,jailbreak",
            description="Comma-separated list of words to block"
        )
        
        case_sensitive: bool = Field(
            default=False,
            description="Make word matching case sensitive"
        )
        
        log_blocked: bool = Field(
            default=True,
            description="Log blocked messages"
        )
    
    def __init__(self):
        """Initialize the pipeline"""
        self.name = "Toxicity Checker Pipeline"
        self.valves = self.Valves()
        self.blocked_count = 0
        self.total_count = 0
    
    async def on_startup(self):
        """Called when the pipeline starts up"""
        print(f"🛡️  {self.name} starting up")
        print(f"   Kill words: {self.valves.kill_words}")
        print(f"   Case sensitive: {self.valves.case_sensitive}")
    
    async def on_shutdown(self):
        """Called when the pipeline shuts down"""
        print(f"🛡️  {self.name} shutting down")
        print(f"   Blocked: {self.blocked_count}/{self.total_count} messages")
    
    def check_toxicity(self, text: str) -> tuple[bool, str]:
        """
        Check if text contains toxic content
        Returns: (is_toxic, matched_word)
        """
        if not self.valves.enabled or not text:
            return False, ""
        
        # Get kill words list
        kill_words = [word.strip() for word in self.valves.kill_words.split(",")]
        
        # Prepare text for checking
        check_text = text if self.valves.case_sensitive else text.lower()
        
        # Check each kill word
        for word in kill_words:
            if not word:  # Skip empty words
                continue
                
            check_word = word if self.valves.case_sensitive else word.lower()
            
            # Simple word boundary check to avoid false positives
            # e.g., don't block "skills" when looking for "kill"
            pattern = r'\b' + re.escape(check_word) + r'\b'
            
            if re.search(pattern, check_text):
                return True, word
        
        return False, ""
    
    def pipe(
        self, 
        user_message: str, 
        model_id: str, 
        messages: List[dict], 
        body: dict
    ) -> Union[str, Generator, Iterator]:
        """
        Main pipeline function - intercept and validate user messages
        
        This is called for EVERY user message before it reaches the model!
        """
        self.total_count += 1
        
        print(f"🔍 Checking message #{self.total_count}: '{user_message[:50]}...'")
        
        # Check for toxic content
        is_toxic, matched_word = self.check_toxicity(user_message)
        
        if is_toxic:
            self.blocked_count += 1
            
            if self.valves.log_blocked:
                print(f"🚫 BLOCKED message #{self.total_count}")
                print(f"   Matched word: '{matched_word}'")
                print(f"   User message: '{user_message[:100]}...'")
                print(f"   Total blocked: {self.blocked_count}/{self.total_count}")
            
            # Return the block message instead of processing
            return self.valves.block_message
        
        print(f"✅ Message #{self.total_count} passed toxicity check")
        
        # If no toxic content, return None to continue normal processing
        # This allows the message to proceed to the actual LLM
        return None

    def get_stats(self) -> dict:
        """Get pipeline statistics"""
        return {
            "total_messages": self.total_count,
            "blocked_messages": self.blocked_count,
            "allowed_messages": self.total_count - self.blocked_count,
            "block_rate": f"{(self.blocked_count/max(1,self.total_count)*100):.1f}%"
        }