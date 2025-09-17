from __future__ import annotations
from anthropic import Anthropic
import json
import os
import re  
from typing import Any, Dict, List, Optional, Union

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment values from .env if present
load_dotenv()

class Pipeline:
    """A minimal pipeline for monitoring RAG in OpenWebUI.

    This class captures key moments in a chat completion lifecycle and reports them to
    AIceberg for monitoring/auditing. It also forwards completion requests to OpenAI's
    Chat Completions API and returns the final model content.
    """

    class Valves(BaseModel):
        """User-configurable knobs (read from environment by default)."""

        AICEBERG_API_URL: str = Field(default="", description="AIceberg events endpoint URL")
        AB_monitoring_profile_U2A: str = Field(
            default="",
            description="AIceberg monitoring profile for user-to-agent"
        )
        AB_monitoring_profile_A2M: str = Field(
            default="",
            description="AIceberg monitoring profile for agent-to-model"
        )
        AICEBERG_PROFILE_ID: str = Field(
            default="",
            description="Fallback AIceberg Profile ID"
        )
        target_model_provider: str = Field(default="openai", description="Model provider: openai or anthropic")
        target_model: str = Field(
            default="gpt-3.5-turbo",
            description="OpenAI/Anthropic chat model to use",
        )
        block_message: str = Field(
            default="Sorry, this content violates our safety policies.",
            description="Message returned when content is blocked",
        )

    def __init__(self) -> None:
        """Initialize the pipeline and load configuration from environment variables."""
        self.name = "Custom AIceberg Monitor with RAG"
        self.OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", "")
        self.AICEBERG_API_KEY=os.getenv("AICEBERG_API_KEY", "")
        self.ANTHROPIC_API_KEY=os.getenv("ANTHROPIC_API_KEY", "")
        
        # Store redacted content for outlet usage
        self.redacted_user_message = None
        self.redacted_assistant_response = None
        
        self.valves = self.Valves(
            AB_monitoring_profile_U2A=os.getenv("AB_monitoring_profile_U2A", ""), #01K46A3Zxxxxxx
            AB_monitoring_profile_A2M=os.getenv("AB_monitoring_profile_A2M", ""), #01K46A3Zxxxxxx
            AICEBERG_PROFILE_ID=os.getenv("AICEBERG_PROFILE_ID", ""),
            AICEBERG_API_URL=os.getenv("AICEBERG_API_URL", "https://test.api.aiceberg.ai/eap/v0/event"),
            target_model_provider=os.getenv("MODEL_PROVIDER", "openai"),
            target_model=os.getenv("TARGET_MODEL", "gpt-3.5-turbo"),
        )

    def update_headers(self):
        """Update cached header/config values from self.valves."""
        self.AICEBERG_API_URL = self.valves.AICEBERG_API_URL
        self.AB_monitoring_profile_U2A = self.valves.AB_monitoring_profile_U2A
        self.AB_monitoring_profile_A2M = self.valves.AB_monitoring_profile_A2M
        self.AICEBERG_PROFILE_ID = self.valves.AICEBERG_PROFILE_ID
        self.target_model = self.valves.target_model
        self.target_model_provider = self.valves.target_model_provider
        self.block_message = self.valves.block_message

    async def on_startup(self):
        """Called when the pipeline starts up"""
        print("AiceMonitor Pipeline starting up")

    async def on_shutdown(self):
        """Called when the pipeline shuts down"""
        print("AiceMonitor Pipeline shutting down")

    async def on_valves_updated(self):
        """executed when valves are updated."""
        self.update_headers()
    
    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        """Capture metadata for processing."""
        # chat_id is used to group messages in a chat session
        # and is not exposed in the pipes, so we capture it here.
        try:
            self.current_chat_id = body.get("metadata", {}).get("chat_id")
            print(f"Captured chat_id: {self.current_chat_id}")
            return body
        except Exception:
            return body

    def _to_text(self, content: Union[str, Dict[str, Any], List[Any]]) -> str:
        """Normalize content to a compact JSON string (or pass through strings)."""
        if isinstance(content, str):
            return content
        try:
            return json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return str(content)

###################   AIceberg prompt details   ##################
# These methods handle calls to AIceberg's event and prompt details APIs.
###############################################################
    def get_prompt_details(self, prompt_id: str) -> dict:
        """Retrieve prompt details including redacted text from AIceberg."""
        headers = {
            "Authorization": self.AICEBERG_API_KEY,
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.get(
                f"https://test.api.aiceberg.ai/ogma_agent/v2/prompt/{prompt_id}",
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            print(f"Prompt details API error: {exc}")
            return {}


###################   AIceberg Monitoring Logic    ##################
# this method handles sending content to AIceberg for monitoring
# and returns the response including any redacted text.
# tiny regex to redact SSN-like patterns in redacted text to mimic the redaction from aiceberg prompt api endpoint
######################################################################

    def check_with_aiceberg(self, content, phase: str, event_id: str = None) -> dict:
        """Send content to AIceberg for monitoring and return response with redacted text."""
        # Configure based on phase
        if phase == "user_query":
            event_type, is_input = "user_agt", True
            used_profile_id = self.valves.AB_monitoring_profile_U2A
        elif phase == "agent_to_model_prompt":
            event_type, is_input = "agt_llm", True  
            used_profile_id = self.valves.AB_monitoring_profile_A2M
        elif phase == "model_response":
            event_type, is_input = "agt_llm", False
            used_profile_id = self.valves.AB_monitoring_profile_A2M
        elif phase == "final_response_to_user":
            event_type, is_input = "user_agt", False
            used_profile_id = self.valves.AB_monitoring_profile_U2A
        else:
            return {"event_result": "passed"}

        payload = {
            "profile_id": used_profile_id,
            "event_type": event_type,
            "forward_to_llm": False,
        }

        text = self._to_text(content)
        if is_input:
            payload["input"] = text
        else:
            payload["input"] = ""
            payload["output"] = text
            if event_id:
                payload["event_id"] = event_id

        headers = {
            "Authorization": self.AICEBERG_API_KEY,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                "https://test.api.aiceberg.ai/eap/v0/event",
                json=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            aiceberg_response = response.json()
            
            # Get redacted text from AIceberg
            if "event_id" in aiceberg_response:
                prompt_details = self.get_prompt_details(aiceberg_response["event_id"])
                if is_input and "prompt" in prompt_details and prompt_details["prompt"]:
                    aiceberg_response["redacted_text"] = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "***", prompt_details["prompt"])
                elif not is_input and "response" in prompt_details and prompt_details["response"]:
                    aiceberg_response["redacted_text"] = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "***", prompt_details["response"])
            
            return aiceberg_response
        except Exception as exc:
            print(f"AIceberg API error ({phase}): {exc}")
            try:
                print(response.text)  # type: ignore[name-defined]
            except Exception:
                pass
            return {"event_result": "passed"}


###################   LLM Call Logic    ##################
# These methods handle calls to OpenAI or Anthropic APIs.
###########################################################

    def _call_openai(self, payload: dict, body: dict) -> str:
        """Send a chat completion request to OpenAI."""
        headers = {
            "Authorization": f"Bearer {self.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()

        if body.get("stream"):
            parts: List[str] = []
            for line in resp.iter_lines(decode_unicode=True):
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            parts.append(delta)
                    except Exception:
                        continue
            return "".join(parts)
        else:
            return resp.json()["choices"][0]["message"]["content"]

    def _call_anthropic(self, payload: dict) -> str:
        """Send a chat completion request to Anthropic using the SDK."""
        print("Calling Anthropic API via SDK...")

        try:
            client = Anthropic(api_key=self.ANTHROPIC_API_KEY)
            messages = payload.get("messages", [])
         
            formatted_messages = []
            for msg in messages:
                if isinstance(msg.get("content"), str):
                    formatted_messages.append({
                        "role": msg["role"],
                        "content": [{"type": "text", "text": msg["content"]}],
                    })
                else:
                    formatted_messages.append(msg)  

            # Make the request
            response = client.messages.create(
                model=self.valves.target_model,
                max_tokens=1000,
                messages=formatted_messages,
            )

            # Extract text blocks
            return "".join(
                block.text for block in response.content if block.type == "text"
            )

        except Exception as e:
            print(f"❌ Anthropic error: {str(e)}")
            return "Sorry, I'm having trouble connecting to the AI service."


##################   Main Pipeline Logic    ##################
# pipe() is called during chat completion processing in OpenWebUI.
# It captures the payload that would be sent to the model, allowing
# for monitoring and redaction before forwarding to the model API.
###############################################################

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ) -> Optional[str]:
        """Main processing pipeline with AIceberg monitoring."""
        
        # Skip internal tasks - Openwebui uses "### Task:" prefix for system tasks to generate 3 similar prompts for user selection. 
        if user_message.startswith("### Task:"):
            return None
        
        # 1) Monitor user input with AIceberg and check for blocking
        query_result = self.check_with_aiceberg(user_message, "user_query")
        print(f"AIceberg user query result: {query_result}")
        if query_result.get("event_result", "passed") == "blocked" or query_result.get("event_result") == "rejected":
            # For blocked content, outlet needs original toxic message to find and replace with placeholder
            blocked_placeholder = "[Content Blocked]"
            self.original_user_message = user_message  # Keep original for outlet matching
            self.redacted_user_message = blocked_placeholder  # Store placeholder for replacement
            return self.valves.block_message
        
        u2a_event_id = query_result.get("event_id")
        redacted_user_message = query_result.get("redacted_text", user_message)
        
        # Store original and redacted messages for outlet
        self.original_user_message = user_message
        self.redacted_user_message = redacted_user_message

        # 2) Openwebui uses payload to pass parameters to LLM API, so we modify it here
        # to replace original user message with redacted version.
        # We also ensure that model is picked from the valves.

        payload = {**body, "model": self.valves.target_model}
        # Popping them to avoid issues with openai API (preventive step to avoid unexpected fields)
        for key in ("user", "chat_id", "title"):
            payload.pop(key, None)

        # Get messages from payload or fallback to messages parameter from pipe, then clean them
        cleaned_messages = (payload.get("messages", messages) or []).copy()
        # Replace original user message with redacted version everywhere
        for msg in cleaned_messages:
            if "content" in msg:
                msg["content"] = msg["content"].replace(user_message, redacted_user_message)

        payload["messages"] = cleaned_messages

        # 4) agent-to-model monitoring (only when RAG adds context)
        a2m_event_id = None
        has_context_tags = any("<context>" in str(msg.get("content", "")) for msg in cleaned_messages)
        
        if has_context_tags:
            # RAG scenario: extract cleaned system + user messages for monitoring
            rag_payload_for_monitoring = []
            
            # Extract already-cleaned system message
            for msg in cleaned_messages:
                if msg.get("role") == "system":
                    rag_payload_for_monitoring.append(msg)
            
            # Extract already-cleaned latest user message
            if cleaned_messages and cleaned_messages[-1].get("role") == "user":
                rag_payload_for_monitoring.append(cleaned_messages[-1])
            
            # Monitor reduced payload with already-redacted content
            ab_message_result = self.check_with_aiceberg(rag_payload_for_monitoring, "agent_to_model_prompt")
            a2m_event_id = ab_message_result.get("event_id")
            
        # else: Simple chat scenario - skip agent-to-model monitoring (same as user→agent)

        # 5) Call LLM with redacted content
        try:
            if self.valves.target_model_provider == "openai":
                print(f"Payload to OpenAI: {payload}")
                response = self._call_openai(payload, body)
            elif self.valves.target_model_provider == "anthropic":
                print(f"Payload to Anthropic: {payload}")
                response = self._call_anthropic(payload)
            else:
                raise ValueError(f"Unsupported provider: {self.valves.target_model_provider}")
        except Exception as exc:
            return f"Error: {str(exc)}"

        # 6) Monitor model response
        redacted_response = response
        if a2m_event_id:
            llm_response_result = self.check_with_aiceberg(response, "model_response", a2m_event_id)
            redacted_response = llm_response_result.get("redacted_text", response)

        # 7) Mirror response monitoring (both profiles should see same original content)
        final_redacted_response = redacted_response
        if u2a_event_id:
            # Send original response to maintain consistent signals across profiles.
            final_result = self.check_with_aiceberg(response, "final_response_to_user", u2a_event_id)
            final_redacted_response = final_result.get("redacted_text", redacted_response)
            
        # Store original and redacted responses for outlet
        self.original_assistant_response = response  # Original LLM response
        self.redacted_assistant_response = final_redacted_response  # AIceberg-redacted version

        return final_redacted_response


######################   Outlet Logic    ##################
# outlet() is called before storing chat messages in the database.
# It allows replacing original user messages and assistant responses
# with their AIceberg-redacted versions for privacy compliance.
###############################################################

    async def outlet(self, body: dict, user: Optional[dict] = None) -> dict:
        """Apply redacted content before database storage."""
        try:
            # Replace original user messages with AIceberg-redacted versions
            messages = body.get("messages", [])
            if messages and hasattr(self, 'original_user_message') and hasattr(self, 'redacted_user_message'):
                for message in messages:
                    if (message.get("role") == "user" and 
                        message.get("content") == self.original_user_message):
                        message["content"] = self.redacted_user_message
                        
            # Replace assistant responses with AIceberg-redacted versions  
            choices = body.get("choices", [])
            if choices and hasattr(self, 'original_assistant_response') and hasattr(self, 'redacted_assistant_response'):
                for choice in choices:
                    message = choice.get("message", {})
                    if (message.get("content") == self.original_assistant_response):
                        message["content"] = self.redacted_assistant_response
                            
            return body
            
        except Exception:
            return body