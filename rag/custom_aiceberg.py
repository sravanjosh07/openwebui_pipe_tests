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
        self.name = "Custom AIceberg Monitor"
        self.OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", "")         #sk-xxxxxx
        self.AICEBERG_API_KEY=os.getenv("AICEBERG_API_KEY", "")     #Bearer eyJraWQxxxxx
        self.ANTHROPIC_API_KEY=os.getenv("ANTHROPIC_API_KEY", "")   
        
        # attributes updated with each request, that help with monitoring and redaction
        self.original_query = None  # original user query
        self.redacted_query = None  # AIceberg-redacted version of the original query
        self.original_response = None  # LLM response
        self.redacted_response = None  # Redacted LLM response for outlet
        
        # Current user->agent event tracking for tool interactions
        self.current_user_agent_event_id = None
        
        self.valves = self.Valves(
            AB_monitoring_profile_U2A=os.getenv("AB_monitoring_profile_U2A", ""), #01K46A3Zxxxxxx
            AB_monitoring_profile_A2M=os.getenv("AB_monitoring_profile_A2M", ""), #01K46A3Zxxxxxx
            AICEBERG_API_URL=os.getenv("AICEBERG_API_URL", "https://prod.api.aiceberg.ai/eap/v0/event"),
            target_model_provider=os.getenv("MODEL_PROVIDER", "openai"), #openai or anthropic
            target_model=os.getenv("TARGET_MODEL", "gpt-3.5-turbo"), #gpt-3.5-turbo, gpt-4, claude-2
        )

    def update_headers(self):
        """Update cached header/config values from self.valves."""
        self.AICEBERG_API_URL = self.valves.AICEBERG_API_URL
        self.AB_monitoring_profile_U2A = self.valves.AB_monitoring_profile_U2A
        self.AB_monitoring_profile_A2M = self.valves.AB_monitoring_profile_A2M
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
        """Capture chat_id for logging purposes."""
        try:
            chat_id = body.get("metadata", {}).get("chat_id")
            print(f"Chat ID: {chat_id}")
            return body
        except Exception:
            return body

    def _to_text(self, content: Union[str, Dict[str, Any], List[Any]]) -> str:
        """Normalize content to a compact JSON string, formatting it to pass to aiceberg."""
        if isinstance(content, str):
            return content
        try:
            return json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return str(content)


#######################   Helper Methods    ##################
# These methods handle text extraction, tool call detection,
# and interaction type detection.
###############################################################

    def _has_tool_calls(self, response) -> bool:
        """Check if LLM response contains tool calls JSON."""
        try:
            # Tool calls response format: {"tool_calls": [{"name": "...", "parameters": {...}}]} or {"tool_calls": []}
            return '"tool_calls"' in str(response)
        except Exception:
            return False

    def _extract_clean_query(self, user_message: str) -> str:
        """Extract clean query from complex user message format."""
        try:
            # Handle tool output format: extract query before the tool output
            if "\nTool `" in user_message and "` Output:" in user_message:
                # Extract the part before the tool output
                parts = user_message.split("\nTool `")
                if len(parts) > 0:
                    return parts[0].strip()
            
            # Handle format like: 'Query: History:\nUSER: """what is the weather in Houston?"""\nQuery: what is the weather in Houston?'
            if "Query: History:" in user_message and 'USER: """' in user_message:
                # Extract the part after the last "Query: "
                parts = user_message.split("Query: ")
                if len(parts) > 1:
                    return parts[-1].strip()
                    
            # Handle other potential formats or return as-is
            return user_message.strip()
        except Exception:
            return user_message.strip()
    
    def _detect_interaction_type(self, user_message: str, messages: List[dict]) -> str:
        """Determine the type of interaction: 'direct', 'rag', 'tool_selection', or 'tool_output'."""
        # Check for tool output processing (Stage 2 of tool interactions)
        if "\nTool `" in user_message and "` Output:" in user_message:
            return "tool_output"
        
        # Check messages for RAG context or tool selection 
        for msg in messages:
            content = str(msg.get("content", ""))
            if msg.get("role") == "system":
                if "<context>" in content:
                    return "rag"  
                elif "Available Tools:" in content:
                    return "tool_selection"
        
        return "direct"  # Simple chat

        
###################   AIceberg prompt details   ##################
# These methods handle calls to AIceberg's event and prompt details APIs.
###############################################################
    def get_prompt_details(self, prompt_id: str) -> dict:
        """Retrieve prompt details including redacted text from AIceberg.
        Aiceberg stores the processed prompts and responses for each event"""
        headers = {
            "Authorization": self.AICEBERG_API_KEY,
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.get(
                f"https://prod.api.aiceberg.ai/ogma_agent/v2/prompt/{prompt_id}",
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
            profile_id_to_use = self.valves.AB_monitoring_profile_U2A
        elif phase == "agent_to_model_prompt":
            event_type, is_input = "agt_llm", True  
            profile_id_to_use = self.valves.AB_monitoring_profile_A2M
        elif phase == "model_response":
            event_type, is_input = "agt_llm", False
            profile_id_to_use = self.valves.AB_monitoring_profile_A2M
        elif phase == "final_response_to_user":
            event_type, is_input = "user_agt", False
            profile_id_to_use = self.valves.AB_monitoring_profile_U2A
        else:
            return {"event_result": "passed"}

        payload = {
            "profile_id": profile_id_to_use,
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

        print(f"AIceberg payload ({phase}): {payload}")
        
        try:
            response = requests.post(
                "https://prod.api.aiceberg.ai/eap/v0/event",
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
                else:
                    # Fallback: use original content if prompt details unavailable
                    print(f"Using original content as fallback for event {aiceberg_response['event_id']}")
                    aiceberg_response["redacted_text"] = self._to_text(content)
            
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
            print(f"Anthropic error: {str(e)}")
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
        """
        Main processing pipeline with AIceberg monitoring.
        
        Handles 4 types of interactions:
        1. Direct chat: user->agent, agent->llm (no context)  
        2. RAG: user->agent, agent->llm (with <context> in system)
        3. Tool selection: user->agent, agent->llm (with Available Tools in system)
        4. Tool output: agent->llm (with Tool Output in user), mirrors to original user->agent
        """
        
        # Skip OpenWebUI internal tasks
        if user_message.startswith("### Task:"):
            return None
        
        # === STEP 1: Determine interaction type and extract clean query ===
        interaction_type = self._detect_interaction_type(user_message, messages)
        self.original_query = self._extract_clean_query(user_message)
        
        print(f"Interaction type: {interaction_type}")
        
        # === STEP 2: Handle user->agent monitoring (only for new user queries) ===
        user_agent_event_id = None
        
        # === STEP 2A: Check if we should reuse existing user->agent event (deduplication) ===
        if interaction_type == "tool_output":
            # Tool output always reuses the original user query event
            user_agent_event_id = self.current_user_agent_event_id
            print(f"Tool output stage - reusing user event: {user_agent_event_id}")
        elif (interaction_type in ["direct", "rag"] and 
              hasattr(self, 'current_user_agent_event_id') and self.current_user_agent_event_id and
              hasattr(self, 'redacted_query') and self.redacted_query == self.original_query):
            # Fallback from tool_selection with same query - reuse existing event
            user_agent_event_id = self.current_user_agent_event_id
            print(f"{interaction_type.title()} fallback - reusing user event: {user_agent_event_id}")
        else:
            # Create new user->agent event
            query_result = self.check_with_aiceberg(self.original_query, "user_query")
            print(f"AIceberg user query result: {query_result}")
            
            if query_result.get("event_result") in ["blocked", "rejected"]:
                self.redacted_query = "[Content Blocked]"
                return self.valves.block_message
            
            user_agent_event_id = query_result.get("event_id")
            self.redacted_query = query_result.get("redacted_text", self.original_query)
            self.current_user_agent_event_id = user_agent_event_id
        
        # === STEP 3: Prepare LLM payload with global redaction ===
        payload = {**body, "model": self.valves.target_model}
        # Remove OpenWebUI-specific fields that could cause API issues
        for key in ("user", "chat_id", "title"):
            payload.pop(key, None)
        
        # Apply global redaction: replace original query with redacted version everywhere
        cleaned_messages = (payload.get("messages", messages) or []).copy()
        if self.original_query and self.redacted_query:
            for msg in cleaned_messages:
                if "content" in msg:
                    msg["content"] = msg["content"].replace(self.original_query, self.redacted_query)
        
        payload["messages"] = cleaned_messages
        
        # === STEP 4: Monitor agent->llm (for RAG and tools) ===
        agent_llm_event_id = None
        
        if interaction_type == "rag":
            # Monitor system context + clean user query (no conversation history, no duplicates)
            monitoring_payload = []
            for msg in cleaned_messages:
                if msg.get("role") == "system":
                    monitoring_payload.append(msg)
            # Add only one clean user query (not repeated for each user message)
            monitoring_payload.append({"role": "user", "content": self.redacted_query})
            result = self.check_with_aiceberg(monitoring_payload, "agent_to_model_prompt")
            agent_llm_event_id = result.get("event_id")
            print(f"Created RAG monitoring event: {agent_llm_event_id}")
            
        elif interaction_type == "tool_selection":
            # Monitor tool list + clean user query (no conversation history)
            monitoring_payload = []
            for msg in cleaned_messages:
                if msg.get("role") == "system":
                    monitoring_payload.append(msg)
                elif msg.get("role") == "user":
                    # Use clean query instead of full message with history
                    monitoring_payload.append({"role": "user", "content": f"Query: {self.redacted_query}"})
            result = self.check_with_aiceberg(monitoring_payload, "agent_to_model_prompt")
            agent_llm_event_id = result.get("event_id")
            print(f"🔧 Created tool selection event: {agent_llm_event_id}")
            
        elif interaction_type == "tool_output":
            # Monitor only the current tool output message, not full conversation history
            monitoring_payload = [{"role": "user", "content": user_message}]
            result = self.check_with_aiceberg(monitoring_payload, "agent_to_model_prompt")
            agent_llm_event_id = result.get("event_id")
            print(f"🛠️ Created tool output event: {agent_llm_event_id}")
        
        # === STEP 5: Call LLM ===
        try:
            if self.valves.target_model_provider == "openai":
                print(f"Payload to OpenAI: {payload}")
                llm_response = self._call_openai(payload, body)
            elif self.valves.target_model_provider == "anthropic":
                print(f"Payload to Anthropic: {payload}")
                llm_response = self._call_anthropic(payload)
            else:
                raise ValueError(f"Unsupported provider: {self.valves.target_model_provider}")
        except Exception as exc:
            return f"Error: {str(exc)}"
        
        # === STEP 6: Monitor LLM response ===
        final_response = llm_response
        if agent_llm_event_id:
            response_result = self.check_with_aiceberg(llm_response, "model_response", agent_llm_event_id)
            if response_result.get("event_result") in ["blocked", "rejected"]:
                return self.valves.block_message
            final_response = response_result.get("redacted_text", llm_response)
            print(f"Logged LLM response to event {agent_llm_event_id}")
        
        # === STEP 7: Mirror final response to user->agent (for meaningful responses) ===
        if user_agent_event_id and interaction_type in ["direct", "rag", "tool_selection", "tool_output"]:
            # Only mirror final responses, not intermediate tool calls
            if not self._has_tool_calls(final_response):
                mirror_result = self.check_with_aiceberg(final_response, "final_response_to_user", user_agent_event_id)
                if mirror_result.get("event_result") in ["blocked", "rejected"]:
                    return self.valves.block_message
                final_response = mirror_result.get("redacted_text", final_response)
                
                # Log appropriate message
                if interaction_type == "tool_output":
                    print(f"Mirrored tool output final response to user event {user_agent_event_id}")
                else:
                    print(f"Mirrored final response to user event {user_agent_event_id}")
            else:
                print(f"Not mirroring tool calls JSON to user->agent")
        
        # === STEP 8: Store for outlet ===
        self.original_response = llm_response
        self.redacted_response = final_response
        
        return final_response


######################   Outlet Logic    ##################
# outlet() is called before storing chat messages in the database.
# It allows replacing original user messages and assistant responses
# with their AIceberg-redacted versions for privacy compliance.
###############################################################

    async def outlet(self, body: dict, user: Optional[dict] = None) -> dict:
        """
        Apply redacted content before database storage.
        
        This ensures that stored conversations contain AIceberg-redacted content
        instead of the original sensitive data.
        """
        try:
            messages = body.get("messages", [])
            
            # Replace user messages: find original query and replace with redacted version
            if messages and self.original_query and self.redacted_query:
                for message in messages:
                    if message.get("role") == "user" and "content" in message:
                        # Global replacement: original query -> redacted query everywhere
                        message["content"] = message["content"].replace(self.original_query, self.redacted_query)
            
            # Replace assistant responses with redacted versions
            choices = body.get("choices", [])
            if choices and self.original_response and self.redacted_response:
                for choice in choices:
                    message = choice.get("message", {})
                    if message.get("content") == self.original_response:
                        message["content"] = self.redacted_response
            
            return body
            
        except Exception as e:
            print(f"Outlet error: {e}")
            return body