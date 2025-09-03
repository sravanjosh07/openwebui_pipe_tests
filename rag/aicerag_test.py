from __future__ import annotations

import json
import os
import re
from typing import List, Optional, Union, Dict, Any
from datetime import datetime

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

class Pipeline:
    """A minimal pipeline for monitoring RAG in OpenWebUI with enhanced tool detection."""

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
        
        # Enhanced logging options
        enable_detailed_logging: bool = Field(
            default=True,
            description="Enable detailed console logging for debugging"
        )
        
        log_tool_calls: bool = Field(
            default=True,
            description="Log tool call detection and monitoring"
        )

    def __init__(self) -> None:
        self.valves = self.Valves(
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
            AICEBERG_API_KEY=os.getenv("AICEBERG_API_KEY", ""),
            AICEBERG_PROFILE_ID=os.getenv("AICEBERG_PROFILE_ID", ""),
        )
        
        # Initialize counters for logging
        self.call_counter = 0
        self.tool_call_counter = 0

    def _log(self, message: str, level: str = "INFO") -> None:
        """Enhanced logging with timestamps and levels"""
        if self.valves.enable_detailed_logging:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] [{level}] {message}")

    def _detect_tool_usage(self, payload: dict) -> tuple[bool, List[str]]:
        """Detect if the request contains tool definitions and extract tool names"""
        tools = payload.get("tools", [])
        if not tools:
            return False, []
        
        tool_names = []
        for tool in tools:
            if isinstance(tool, dict) and "function" in tool:
                func_name = tool["function"].get("name", "unknown")
                tool_names.append(func_name)
        
        return len(tool_names) > 0, tool_names

    def _detect_tool_response(self, response_text: str) -> bool:
        """Detect if the response contains tool call results"""
        # Look for common patterns that indicate tool usage
        tool_patterns = [
            r"function_call",
            r"tool_calls",
            r"Using tool:",
            r"Calling function:",
            r"Tool result:",
            r"Function executed:",
            # Add patterns based on your specific tools
            r"calculated?.*=.*\d+",
            r"search.*results?",
            r"web.*search",
        ]
        
        for pattern in tool_patterns:
            if re.search(pattern, response_text, re.IGNORECASE):
                return True
        return False

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

        Enhanced phases for tool monitoring:
          - 'user_query'         -> user_agt (input) - User's original question
          - 'complete_prompt'    -> agt_llm (input) - Complete request with tools
          - 'tool_aware_prompt'  -> agt_llm (input) - Request that includes tool definitions
          - 'model_response'     -> agt_llm (output) - LLM's reply with tool results
          - 'tool_enhanced_response' -> agt_llm (output) - Response enhanced by tool calls
          - 'llm_response'       -> user_agt (output) - Final response to user
        """
        phase_config = {
            "user_query":              {"event_type": "user_agt", "is_input": True,  "metadata": {"content_type": "user_message"}},
            "complete_prompt":         {"event_type": "agt_llm",  "is_input": True,  "metadata": {"content_type": "complete_prompt_bundle"}},
            "tool_aware_prompt":       {"event_type": "agt_llm",  "is_input": True,  "metadata": {"content_type": "tool_enabled_prompt"}},
            "model_response":          {"event_type": "agt_llm",  "is_input": False, "metadata": {"content_type": "model_reply"}},
            "tool_enhanced_response":  {"event_type": "agt_llm",  "is_input": False, "metadata": {"content_type": "tool_enhanced_reply"}},
            "llm_response":            {"event_type": "user_agt", "is_input": False, "metadata": {"content_type": "model_reply_mirror"}},
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
        
        self._log(f"🔄 AIceberg API call - Phase: {phase}, Content length: {len(text)}")
        
        try:
            response = requests.post(
                "https://test.api.aiceberg.ai/eap/v0/event",
                json=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            
            self._log(f"✅ AIceberg response - Event ID: {result.get('event_id', 'N/A')}, Result: {result.get('event_result', 'N/A')}")
            
            return result
        except Exception as exc:
            self._log(f"❌ AIceberg API error ({phase}): {exc}", "ERROR")
            try:
                if 'response' in locals():
                    self._log(f"Response text: {response.text}", "ERROR")
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
        """Intercept and monitor a chat completion request with enhanced tool detection."""
        self.call_counter += 1
        
        self._log("=" * 60)
        self._log(f"🚀 RAG MONITOR CALL #{self.call_counter} - ENHANCED TOOL DETECTION")
        self._log(f"📝 User message: {user_message}")
        self._log(f"🤖 Model: {model_id}")
        self._log(f"📊 Messages count: {len(messages)}")
        
        # Skip internal synthetic tasks
        if user_message.startswith("### Task:"):
            self._log("⏭️ Skipping internal OpenWebUI task")
            return None

        # 1) Record user query -> user_agt (input)
        query_result = self.check_with_aiceberg(user_message, "user_query")
        if query_result.get("event_result", "passed") == "rejected":
            self._log("🚫 User query BLOCKED by AIceberg", "WARN")
            return self.valves.block_message
        query_event_id = query_result.get("event_id")

        # 2) Prepare the exact payload for the LLM
        payload = {**body, "model": self.valves.target_model}
        payload.pop("user", None)
        payload.pop("chat_id", None)
        payload.pop("title", None)

        rag_only_payload = payload.get("messages", messages) or []
        
        # 3) Enhanced tool detection
        has_tools, tool_names = self._detect_tool_usage(payload)
        
        if has_tools and self.valves.log_tool_calls:
            self.tool_call_counter += 1
            self._log(f"🛠️ TOOL DETECTION #{self.tool_call_counter}", "TOOL")
            self._log(f"🔧 Available tools: {', '.join(tool_names)}", "TOOL")
            
            # Use tool-aware monitoring phase
            bundle_result = self.check_with_aiceberg(
                content=rag_only_payload,
                phase="tool_aware_prompt",
                extra_metadata={
                    "has_tools": True,
                    "tool_names": tool_names,
                    "tool_count": len(tool_names)
                }
            )
        else:
            self._log("📝 No tools detected - standard prompt")
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
        
        self._log(f"🤖 Calling OpenAI API...")
        
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
                
            self._log(f"✅ OpenAI response received ({len(openai_response)} chars)")
            
        except Exception as exc:
            self._log(f"❌ OpenAI error: {exc}", "ERROR")
            return f"Error: {str(exc)}"

        # 5) Enhanced response monitoring with tool detection
        tool_used_in_response = self._detect_tool_response(openai_response)
        
        if tool_used_in_response and self.valves.log_tool_calls:
            self._log("🔧 Tool usage detected in response!", "TOOL")
            
        if agt_event_id:
            if has_tools and tool_used_in_response:
                # Monitor as tool-enhanced response
                self.check_with_aiceberg(
                    content=openai_response,
                    phase="tool_enhanced_response",
                    event_id=agt_event_id,
                    extra_metadata={
                        "tool_used": True,
                        "available_tools": tool_names,
                        "response_length": len(openai_response)
                    }
                )
            else:
                # Standard model response monitoring
                self.check_with_aiceberg(
                    content=openai_response,
                    phase="model_response",
                    event_id=agt_event_id,
                )

        # 6) Optional mirror as user_agt output for legacy linkage
        if self.valves.emit_user_llm_output_mirror and query_event_id:
            self.check_with_aiceberg(
                content=openai_response,
                phase="llm_response",
                event_id=query_event_id,
            )

        self._log(f"🏁 Pipeline call #{self.call_counter} completed")
        self._log("=" * 60)
        
        return openai_response