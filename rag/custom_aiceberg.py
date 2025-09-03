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
            description=" ab_monitoring_profile_U2A Profile ID"
        )
        AB_monitoring_profile_A2M: str = Field(
            default="",
            description=" ab_monitoring_profile_A2M Profile ID"
        )
        AICEBERG_PROFILE_ID: str = Field(
            default="",
            description="Fallback AIceberg Profile ID"
        )
        target_model_provider: str = Field(default="openai", description="Model provider: openai or anthropic")
        target_model: str = Field(
            default="gpt-3.5-turbo",
            description="OpenAI/Anthropic chat model to use (e.g. gpt-3.5-turbo, claude-sonnet-4-20250514)",
        )
        emit_user_llm_output_mirror: bool = Field(
            default=True,
            description="Also mirror model reply as user_agt output (for legacy linking)",
        )
        block_message: str = Field(
            default="Sorry, this content violates our safety policies.",
            description="Message returned when content is blocked",
        )

    def __init__(self) -> None:
        """Initialize the pipeline and load configuration from environment variables."""
        self.name = "AiceMonitor_clean"
        self.OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", "")
        self.AICEBERG_API_KEY=os.getenv("AICEBERG_API_KEY", "")
        self.ANTHROPIC_API_KEY=os.getenv("ANTHROPIC_API_KEY", "")
        self.valves = self.Valves(
            AB_monitoring_profile_U2A=os.getenv("AB_monitoring_profile_U2A", ""),
            AB_monitoring_profile_A2M=os.getenv("AB_monitoring_profile_A2M", ""),
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
        self.emit_user_llm_output_mirror = self.valves.emit_user_llm_output_mirror
        self.block_message = self.valves.block_message

    async def on_startup(self):
        """Called when the pipeline starts up"""
        print(f"🚀 AiceMonitor Pipeline starting up")

    async def on_shutdown(self):
        """Called when the pipeline shuts down"""
        print("🛑 AiceMonitor Pipeline shutting down")

    async def on_valves_updated(self):
        """executed when valves are updated."""
        self.update_headers()    

    def _to_text(self, content: Union[str, Dict[str, Any], List[Any]]) -> str:
        """Normalize content to a compact JSON string (or pass through strings)."""
        if isinstance(content, str):
            return content
        try:
            return json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return str(content)

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

    def check_with_aiceberg(
        self,
        content: Union[str, Dict[str, Any], List[Any]],
        phase: str,
        event_id: Optional[str] = None,
        extra_metadata: Optional[dict] = None,
        profile_id: Optional[str] = None,
    ) -> dict:
        """Send content to AIceberg for monitoring and return the JSON response."""
        phase_config = {
            "user_query": {
                "event_type": "user_agt",
                "is_input": True,
                "metadata": {"content_type": "user_message"},
                "profile_id": self.valves.AB_monitoring_profile_U2A,
            },
            "complete_prompt": {
                "event_type": "agt_llm",
                "is_input": True,
                "metadata": {"content_type": "complete_prompt_bundle"},
                "profile_id": self.valves.AB_monitoring_profile_A2M,
            },
            "model_response": {
                "event_type": "agt_llm",
                "is_input": False,
                "metadata": {"content_type": "model_reply"},
                "profile_id": self.valves.AB_monitoring_profile_A2M,
            },
            "llm_response": {
                "event_type": "user_agt",
                "is_input": False,
                "metadata": {"content_type": "model_reply_mirror"},
                "profile_id": self.valves.AB_monitoring_profile_U2A,
            },
        }
        config = phase_config.get(phase, {"event_type": "user_agt", "is_input": True})

        # Use provided profile_id, config profile_id, or fallback to general profile
        used_profile_id = profile_id or config.get("profile_id") or self.valves.AICEBERG_PROFILE_ID
        
        payload: Dict[str, Any] = {
            "profile_id": used_profile_id,
            "event_type": config["event_type"],
            "forward_to_llm": False,
            "metadata": {"rag_phase": phase},
        }

        # Merge phase-specific and extra metadata
        if "metadata" in config:
            payload["metadata"].update(config["metadata"])
        if extra_metadata:
            payload["metadata"].update(extra_metadata)

        text = self._to_text(content)
        if config["is_input"]:
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
            
            # Get redacted text for both inputs and outputs
            if "prompt_id" in aiceberg_response:
                prompt_details = self.get_prompt_details(aiceberg_response["prompt_id"])
                if config["is_input"] and "prompt" in prompt_details:
                    aiceberg_response["redacted_text"] = prompt_details["prompt"]
                elif not config["is_input"] and "response" in prompt_details:
                    aiceberg_response["redacted_text"] = prompt_details["response"]
            
            return aiceberg_response
        except Exception as exc:
            print(f"AIceberg API error ({phase}): {exc}")
            try:
                print(response.text)  # type: ignore[name-defined]
            except Exception:
                pass
            return {"event_result": "passed"}

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

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ) -> Optional[str]:
        """Monitor and route chat completions to OpenAI or Anthropic."""

        print("--- RAG MONITOR (BUNDLE-STYLE) ---")
        print(f"User message: {user_message}")

        # Skip internal synthetic tasks
        if user_message.startswith("### Task:"):
            print("Skipping internal task without RAG context.")
            return None

        # 1) Record user query and get redacted text
        query_result = self.check_with_aiceberg(user_message, "user_query")
        if query_result.get("event_result", "passed") == "rejected":
            return self.valves.block_message
        query_event_id = query_result.get("event_id")
        redacted_user_message = query_result.get("redacted_text", user_message)

        # 2) Build LLM payload with redacted content
        payload = {**body, "model": self.valves.target_model}
        for key in ("user", "chat_id", "title"):
            payload.pop(key, None)

        # Update messages with redacted content
        updated_messages = (payload.get("messages", messages) or []).copy()
        if updated_messages and updated_messages[-1].get("role") == "user":
            updated_messages[-1]["content"] = redacted_user_message
        payload["messages"] = updated_messages

        bundle_result = self.check_with_aiceberg(updated_messages, "complete_prompt")
        agt_event_id = bundle_result.get("event_id")

        # 3) Call provider
        try:
            if self.valves.target_model_provider == "openai":
                response = self._call_openai(payload, body)
            elif self.valves.target_model_provider == "anthropic":
                response = self._call_anthropic(payload)
            else:
                raise ValueError(f"Unsupported provider: {self.valves.target_model_provider}")
        except Exception as exc:
            print(f"LLM error: {exc}")
            return f"Error: {str(exc)}"

        # 4) Record model response and get redacted version
        redacted_response = response
        if agt_event_id:
            response_result = self.check_with_aiceberg(response, "model_response", agt_event_id)
            redacted_response = response_result.get("redacted_text", response)

        # 5) Mirror response for legacy linkage
        if self.valves.emit_user_llm_output_mirror and query_event_id:
            self.check_with_aiceberg(redacted_response, "llm_response", query_event_id)

        return redacted_response