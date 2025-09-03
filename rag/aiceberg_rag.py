from __future__ import annotations

"""
OpenWebUI RAG Monitor Pipeline (cleaned & documented)
----------------------------------------------------
Notes:
- Behavior is unchanged from the original; updates are cosmetic (formatting, docstrings,
  comment clarity) to make the code easier to read/maintain.
- Keep environment variables in a .env file for convenience.
- AIceberg endpoint is configurable via AICEBERG_API_URL (defaults to test endpoint).
- Target model is configurable via OPENAI_TARGET_MODEL (defaults to gpt-3.5-turbo).

Phases used with AIceberg monitoring:
  - user_query      -> user_agt (input)
  - complete_prompt -> agt_llm (input)   # entire request sent to LLM
  - model_response  -> agt_llm (output)  # LLM's reply (reverse of agt_llm)
  - llm_response    -> user_agt (output) # mirrored for top-level UI linkage
"""

import json
import os
import re  # kept (even if unused) to preserve original import set
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

        OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
        AICEBERG_API_KEY: str = Field(default="", description="AIceberg API key")
        AICEBERG_PROFILE_ID: str = Field(default="", description="AIceberg profile ID")
        AICEBERG_API_URL: str = Field(default="", description="AIceberg events endpoint URL")

        block_message: str = Field(
            default="Sorry, this content violates our safety policies.",
            description="Message returned when content is blocked",
        )
        target_model: str = Field(
            default="gpt-3.5-turbo",
            description="OpenAI chat model to use (e.g. gpt-3.5-turbo, gpt-4o)",
        )
        emit_user_llm_output_mirror: bool = Field(
            default=True,
            description="Also mirror model reply as user_agt output (for legacy linking)",
        )

    def __init__(self) -> None:
        # Initialize valves from environment variables
        self.valves = self.Valves(
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
            AICEBERG_API_KEY=os.getenv("AICEBERG_API_KEY", ""),
            AICEBERG_PROFILE_ID=os.getenv("AICEBERG_PROFILE_ID", ""),
            AICEBERG_API_URL=os.getenv("AICEBERG_API_URL", "https://test.api.aiceberg.ai/eap/v0/event"),
            target_model=os.getenv("OPENAI_TARGET_MODEL", "gpt-3.5-turbo"),
        )

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def _to_text(self, content: Union[str, Dict[str, Any], List[Any]]) -> str:
        """Normalize content to a compact JSON string (or pass through strings).

        This ensures payload size stays predictable while preserving readability.
        """
        if isinstance(content, str):
            return content
        try:
            # Compact JSON: keep keys but remove extra whitespace
            return json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            # Fallback to string representation if serialization fails
            return str(content)

    # ---------------------------------------------------------------------
    # AIceberg Monitoring
    # ---------------------------------------------------------------------
    def get_prompt_details(self, event_id: str) -> Optional[dict]:
        """Fetch detailed prompt analysis using event_id from a previous monitoring call.
        
        Args:
            event_id: The event_id returned from a previous check_with_aiceberg call
            
        Returns:
            Detailed analysis dict from the prompt API, or None on failure
        """
        url = f"https://test.api.aiceberg.ai/ogma_agent/v2/prompt/{event_id}"
        headers = {
            "Authorization": self.valves.AICEBERG_API_KEY,
            "Accept": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            print(f"Failed to fetch prompt details for {event_id}: {exc}")
            return None

    def check_with_aiceberg(
        self,
        content: Union[str, Dict[str, Any], List[Any]],
        phase: str,
        event_id: Optional[str] = None,
        extra_metadata: Optional[dict] = None,
    ) -> dict:
        """Send content to AIceberg for monitoring and return the JSON response.

        Args:
            content: The payload to record (string or JSON-serializable).
            phase: One of {user_query, complete_prompt, model_response, llm_response}.
            event_id: Optional correlation ID for output events (links to input).
            extra_metadata: Additional key-value data to include in the event.

        Returns:
            Parsed JSON response from AIceberg (dict). On failure, returns a
            default {"event_result": "passed"}. For input events, always includes
            'processed_content' field with Aiceberg's processed version.
        """
        phase_config = {
            "user_query": {
                "event_type": "user_agt",
                "is_input": True,
                "metadata": {"content_type": "user_message"},
            },
            "complete_prompt": {
                "event_type": "agt_llm",
                "is_input": True,
                "metadata": {"content_type": "complete_prompt_bundle"},
            },
            "model_response": {
                "event_type": "agt_llm",
                "is_input": False,
                "metadata": {"content_type": "model_reply"},
            },
            "llm_response": {
                "event_type": "user_agt",
                "is_input": False,
                "metadata": {"content_type": "model_reply_mirror"},
            },
        }
        config = phase_config.get(phase, {"event_type": "user_agt", "is_input": True})

        payload: Dict[str, Any] = {
            "profile_id": self.valves.AICEBERG_PROFILE_ID,
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
            "Authorization": self.valves.AICEBERG_API_KEY,
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
            result = response.json()
            
            # Always fetch prompt details for all events (cheap DB lookup)
            if result.get("event_id"):
                details = self.get_prompt_details(result["event_id"])
                if details:
                    result["details"] = details
                    # For input events, extract processed content
                    if config["is_input"]:
                        processed_prompt = details.get("prompt", "")
                        if processed_prompt:
                            result["processed_content"] = processed_prompt
                            # Log if content was modified
                            if processed_prompt != text:
                                print(f"Aiceberg processed content: {text} -> {processed_prompt}")
                    # For output events, we could potentially use processed response too
                    else:
                        processed_response = details.get("response", "")
                        if processed_response and processed_response != text:
                            result["processed_content"] = processed_response
                            print(f"Aiceberg processed response: {text} -> {processed_response}")
            
            return result
        except Exception as exc:
            # Log and fail-open to avoid blocking user flows on telemetry issues
            print(f"AIceberg API error ({phase}): {exc}")
            try:
                print(response.text)  # type: ignore[name-defined]
            except Exception:
                pass
            return {"event_result": "passed"}

    # ---------------------------------------------------------------------
    # Main pipe entrypoint
    # ---------------------------------------------------------------------
    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ) -> Optional[str]:
        """Intercept and monitor a chat completion request.

        Flow:
          1) Record the user's query (user_agt input). If rejected, return block_message.
          2) Build the exact LLM payload, removing OWUI-only keys; record bundle (agt_llm input).
          3) Call OpenAI Chat Completions (streaming or non-streaming).
          4) Record the model's reply as agt_llm output (linked via event_id when present).
          5) Optionally mirror the reply as user_agt output for legacy linkage.
        """
        print("--- RAG MONITOR (BUNDLE-STYLE) ---")
        print(f"User message: {user_message}")
        print(f"body: {body}")
        print(f"Model: {model_id}")
        print(f"Messages: {messages}")

        # Skip internal synthetic tasks that shouldn't be monitored
        if user_message.startswith("### Task:"):
            print("Skipping internal task without RAG context.")
            return None

        # 1) Record user query -> user_agt (input) and get processed content
        query_result = self.check_with_aiceberg(user_message, "user_query")
        if query_result.get("event_result", "passed") == "rejected":
            return self.valves.block_message
        query_event_id = query_result.get("event_id")

        # Use Aiceberg's processed content if available, otherwise use original
        updated_user_message = query_result.get("processed_content", user_message)

        # 2) Prepare the *exact* payload we'll send to the LLM
        #    (remove OWUI-specific keys that OpenAI won't accept)
        payload = {**body, "model": self.valves.target_model}
        payload.pop("user", None)
        payload.pop("chat_id", None)
        payload.pop("title", None)

        # Update the messages with Aiceberg's processed user content
        rag_only_payload = payload.get("messages", messages) or []
        if rag_only_payload:
            # Find and update the user's message in the conversation
            for msg in reversed(rag_only_payload):
                if msg.get("role") == "user":
                    msg["content"] = updated_user_message
                    break

        bundle_result = self.check_with_aiceberg(
            content=rag_only_payload,
            phase="complete_prompt",
        )
        agt_event_id = bundle_result.get("event_id")

        # 3) Call the LLM (OpenAI Chat Completions)
        headers = {
            "Authorization": f"Bearer {self.valves.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()

            # Handle streaming responses by concatenating deltas
            if body.get("stream"):
                content_parts: List[str] = []
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
                                content_parts.append(delta)
                        except Exception:
                            # Ignore malformed chunks; keep streaming
                            pass
                openai_response = "".join(content_parts)
            else:
                openai_response = resp.json()["choices"][0]["message"]["content"]

        except Exception as exc:
            print(f"OpenAI error: {exc}")
            return f"Error: {str(exc)}"

        # 4) Mirror reply as reverse of agt_llm -> llm_agt (output)
        if agt_event_id:
            self.check_with_aiceberg(
                content=openai_response,
                phase="model_response",
                event_id=agt_event_id,
            )

        # 5) (Optional) also mirror as user_agt output for legacy linkage
        if self.valves.emit_user_llm_output_mirror and query_event_id:
            self.check_with_aiceberg(
                content=openai_response,
                phase="llm_response",
                event_id=query_event_id,
            )

        return openai_response
