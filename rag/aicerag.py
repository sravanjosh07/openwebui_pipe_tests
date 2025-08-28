from __future__ import annotations

import json
import os
import re
from typing import List, Optional, Union, Dict, Any

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

class Pipeline:
    """A minimal pipeline for monitoring RAG in OpenWebUI."""

    class Valves(BaseModel):
        OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
        AICEBERG_API_KEY: str = Field(default="", description="AIceberg API key")
        AICEBERG_PROFILE_ID: str = Field(default="", description="AIceberg profile ID")
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
        self.valves = self.Valves(
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
            AICEBERG_API_KEY=os.getenv("AICEBERG_API_KEY", ""),
            AICEBERG_PROFILE_ID=os.getenv("AICEBERG_PROFILE_ID", ""),
        )

    def _to_text(self, content: Union[str, Dict[str, Any], List[Any]]) -> str:
        """Normalize content to a string for API transport."""
        if isinstance(content, str):
            return content
        try:
            # compact to reduce payload size but keep readability keys
            return json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return str(content)

    def check_with_aiceberg(
        self,
        content: Union[str, Dict[str, Any], List[Any]],
        phase: str,
        event_id: Optional[str] = None,
        extra_metadata: Optional[dict] = None,
    ) -> dict:
        """
        Send content to AIceberg for monitoring and return the response.

        Phases supported now:
          - 'user_query'      -> user_agt (input)
          - 'complete_prompt' -> agt_llm (input)   # entire request sent to LLM
          - 'model_response'  -> agt_llm (output)  # LLM's reply (reverse of agt_llm)
          - 'llm_response'    -> user_agt (output) # mirroring for top-level UI link
        """
        phase_config = {
            "user_query":      {"event_type": "user_agt", "is_input": True,  "metadata": {"content_type": "user_message"}},
            "complete_prompt": {"event_type": "agt_llm",  "is_input": True,  "metadata": {"content_type": "complete_prompt_bundle"}},
            "model_response":  {"event_type": "agt_llm",  "is_input": False, "metadata": {"content_type": "model_reply"}},
            "llm_response":    {"event_type": "user_agt", "is_input": False, "metadata": {"content_type": "model_reply_mirror"}},
        }
        config = phase_config.get(phase, {"event_type": "user_agt", "is_input": True})
        payload = {
            "profile_id": self.valves.AICEBERG_PROFILE_ID,
            "event_type": config["event_type"],
            "forward_to_llm": False,
            "metadata": {"rag_phase": phase},
        }
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
            return response.json()
        except Exception as exc:
            print(f"AIceberg API error ({phase}): {exc}")
            try:
                print(response.text)  # type: ignore[name-defined]
            except Exception:
                pass
            return {"event_result": "passed"}

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ) -> Union[str, None]:
        """Intercept and monitor a chat completion request."""
        print("--- RAG MONITOR (BUNDLE-STYLE) ---")
        print(f"User message: {user_message}")

        # Skip internal synthetic tasks
        if user_message.startswith("### Task:"):
            print("Skipping internal task without RAG context.")
            return None

        # 1) Record user query -> user_llm (input)
        query_result = self.check_with_aiceberg(user_message, "user_query")
        if query_result.get("event_result", "passed") == "rejected":
            return self.valves.block_message
        query_event_id = query_result.get("event_id")

        # 2) Prepare the *exact* payload we'll send to the LLM
        #    (remove OWUI-specific keys that OpenAI won't accept)
        payload = {**body, "model": self.valves.target_model}
        payload.pop("user", None)
        payload.pop("chat_id", None)
        payload.pop("title", None)

        rag_only_payload = payload.get("messages", messages) or []
        
        bundle_result = self.check_with_aiceberg(
            content=rag_only_payload,
            phase="complete_prompt",
        )
        agt_event_id = bundle_result.get("event_id")

        # 4) Call the LLM
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
            if body.get("stream"):
                content_parts: List[str] = []
                for line in resp.iter_lines(decode_unicode=True):
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                content_parts.append(delta)
                        except Exception:
                            pass
                openai_response = "".join(content_parts)
            else:
                openai_response = resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            print(f"OpenAI error: {exc}")
            return f"Error: {str(exc)}"

        # 5) Mirror reply as reverse of agt_llm -> llm_agt (output)
        if agt_event_id:
            self.check_with_aiceberg(
                content=openai_response,
                phase="model_response",
                event_id=agt_event_id,
            )

        # 6) (Optional) also mirror as user_llm output for legacy linkage
        if self.valves.emit_user_llm_output_mirror and query_event_id:
            self.check_with_aiceberg(
                content=openai_response,
                phase="llm_response",
                event_id=query_event_id,
            )

        return openai_response