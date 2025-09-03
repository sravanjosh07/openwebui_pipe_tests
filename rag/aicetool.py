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
    """A pipeline for monitoring Tool-based workflows in OpenWebUI."""

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
        
        enable_tool_monitoring: bool = Field(
            default=True,
            description="Enable detailed monitoring of tool interactions",
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

    def _detect_workflow_type(self, user_message: str, messages: List[dict]) -> str:
        """Detect if this is a tool-based workflow or standard workflow."""
        # Check for tool output patterns in user message
        if "Tool `" in user_message and "` Output:" in user_message:
            return "tool_execution"
        
        # Check for tool calls in recent messages
        for msg in messages[-3:]:  # Check last 3 messages
            content = msg.get("content", "")
            if isinstance(content, str) and ("tool_calls" in content or "get_current_weather" in content):
                return "tool_planning"
        
        # Default to standard workflow
        return "standard"

    def check_with_aiceberg(
        self,
        content: Union[str, Dict[str, Any], List[Any]],
        phase: str,
        event_id: Optional[str] = None,
        extra_metadata: Optional[dict] = None,
    ) -> dict:
        """
        Send content to AIceberg for monitoring and return the response.

        Phases supported:
          - 'user_query'         -> user_agt (input)
          - 'tool_planning'      -> agt_llm (input)   # LLM decides which tool to use
          - 'tool_selection'     -> agt_llm (output)  # LLM's tool selection response
          - 'tool_execution'     -> agt_tool (input)  # Input to tool
          - 'tool_result'        -> agt_tool (output) # Tool's output
          - 'result_synthesis'   -> agt_llm (input)   # Tool result sent to LLM for synthesis
          - 'final_response'     -> agt_llm (output)  # LLM's final synthesized response
          - 'user_response'      -> user_agt (output) # Mirror for user interface
          - 'standard_query'     -> user_llm (input)  # Standard user query
          - 'standard_response'  -> user_llm (output) # Standard LLM response
        """
        phase_config = {
            # Tool workflow phases
            "user_query":         {"event_type": "user_agt", "is_input": True,  "metadata": {"content_type": "user_message"}},
            "tool_planning":      {"event_type": "agt_llm",  "is_input": True,  "metadata": {"content_type": "tool_planning_request"}},
            "tool_selection":     {"event_type": "agt_llm",  "is_input": False, "metadata": {"content_type": "tool_selection_response"}},
            "tool_execution":     {"event_type": "agt_tool", "is_input": True,  "metadata": {"content_type": "tool_input"}},
            "tool_result":        {"event_type": "agt_tool", "is_input": False, "metadata": {"content_type": "tool_output"}},
            "result_synthesis":   {"event_type": "agt_llm",  "is_input": True,  "metadata": {"content_type": "tool_result_synthesis"}},
            "final_response":     {"event_type": "agt_llm",  "is_input": False, "metadata": {"content_type": "final_synthesized_response"}},
            "user_response":      {"event_type": "user_agt", "is_input": False, "metadata": {"content_type": "final_user_response"}},
            
            # Standard workflow phases
            "standard_query":     {"event_type": "user_llm", "is_input": True,  "metadata": {"content_type": "user_query"}},
            "standard_response":  {"event_type": "user_llm", "is_input": False, "metadata": {"content_type": "llm_response"}},
        }
        
        config = phase_config.get(phase, {"event_type": "user_agt", "is_input": True, "metadata": {}})
        payload = {
            "profile_id": self.valves.AICEBERG_PROFILE_ID,
            "event_type": config["event_type"],
            "forward_to_llm": False,
            "metadata": {"workflow_phase": phase},
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

    def _extract_tool_info(self, user_message: str) -> Dict[str, str]:
        """Extract tool name and output from a tool execution message."""
        tool_info = {"tool_name": "", "tool_output": "", "tool_input": ""}
        
        # Pattern: Tool `tool_name` Output: content
        tool_pattern = r"Tool `([^`]+)` Output:\s*(.*)"
        match = re.search(tool_pattern, user_message, re.DOTALL)
        
        if match:
            tool_info["tool_name"] = match.group(1)
            tool_info["tool_output"] = match.group(2).strip()
            
            # Try to extract tool input from context if available
            # This might need adjustment based on your specific format
            if "parameters" in user_message:
                param_pattern = r'"parameters":\s*({[^}]+})'
                param_match = re.search(param_pattern, user_message)
                if param_match:
                    tool_info["tool_input"] = param_match.group(1)
        
        return tool_info

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ) -> Union[str, None]:
        """Intercept and monitor chat completion requests for Tool workflows."""
        
        # Skip internal synthetic tasks
        if user_message.startswith("### Task:"):
            print("Skipping internal task without monitoring context.")
            return None

        workflow_type = self._detect_workflow_type(user_message, messages)
        print(f"--- WORKFLOW MONITOR ({workflow_type.upper()}) ---")
        print(f"User message: {user_message[:100]}...")

        if workflow_type == "tool_execution":
            return self._handle_tool_execution(user_message, model_id, messages, body)
        elif workflow_type == "tool_planning":
            return self._handle_tool_planning(user_message, model_id, messages, body)
        else:
            return self._handle_standard_workflow(user_message, model_id, messages, body)

    def _handle_tool_execution(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, None]:
        """Handle tool execution workflow monitoring."""
        
        # 1) Record user query (should have been done in planning phase, but ensure it's tracked)
        query_result = self.check_with_aiceberg(user_message, "user_query")
        if query_result.get("event_result", "passed") == "rejected":
            return self.valves.block_message
        query_event_id = query_result.get("event_id")
        
        # 2) Extract tool information
        tool_info = self._extract_tool_info(user_message)
        
        # 3) Record tool execution input
        tool_exec_result = self.check_with_aiceberg(
            content=tool_info.get("tool_input", ""),
            phase="tool_execution",
            extra_metadata={"tool_name": tool_info.get("tool_name", "unknown")}
        )
        tool_exec_event_id = tool_exec_result.get("event_id")
        
        # 4) Record tool output
        if tool_exec_event_id:
            self.check_with_aiceberg(
                content=tool_info.get("tool_output", ""),
                phase="tool_result",
                event_id=tool_exec_event_id,
                extra_metadata={"tool_name": tool_info.get("tool_name", "unknown")}
            )
        
        # 5) Prepare payload for LLM synthesis
        payload = {**body, "model": self.valves.target_model}
        payload.pop("user", None)
        payload.pop("chat_id", None)
        payload.pop("title", None)
        
        # 6) Record synthesis request
        synthesis_result = self.check_with_aiceberg(
            content=payload.get("messages", messages) or [],
            phase="result_synthesis",
            extra_metadata={"tool_name": tool_info.get("tool_name", "unknown")}
        )
        synthesis_event_id = synthesis_result.get("event_id")
        
        # 7) Call LLM for response synthesis
        openai_response = self._call_openai(payload, body)
        if openai_response.startswith("Error:"):
            return openai_response
            
        # 8) Record final LLM response
        if synthesis_event_id:
            self.check_with_aiceberg(
                content=openai_response,
                phase="final_response",
                event_id=synthesis_event_id,
                extra_metadata={"tool_name": tool_info.get("tool_name", "unknown")}
            )
        
        # 9) Mirror final response to user
        if self.valves.emit_user_llm_output_mirror and query_event_id:
            self.check_with_aiceberg(
                content=openai_response,
                phase="user_response",
                event_id=query_event_id,
            )
        
        return openai_response

    def _handle_tool_planning(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, None]:
        """Handle tool planning workflow monitoring."""
        
        # 1) Record user query
        query_result = self.check_with_aiceberg(user_message, "user_query")
        if query_result.get("event_result", "passed") == "rejected":
            return self.valves.block_message
        query_event_id = query_result.get("event_id")
        
        # 2) Prepare payload for tool planning
        payload = {**body, "model": self.valves.target_model}
        payload.pop("user", None)
        payload.pop("chat_id", None)
        payload.pop("title", None)
        
        # 3) Record tool planning request
        planning_result = self.check_with_aiceberg(
            content=payload.get("messages", messages) or [],
            phase="tool_planning"
        )
        planning_event_id = planning_result.get("event_id")
        
        # 4) Call LLM for tool selection
        openai_response = self._call_openai(payload, body)
        if openai_response.startswith("Error:"):
            return openai_response
            
        # 5) Record tool selection response
        if planning_event_id:
            self.check_with_aiceberg(
                content=openai_response,
                phase="tool_selection",
                event_id=planning_event_id,
            )
        
        return openai_response

    def _handle_standard_workflow(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, None]:
        """Handle standard workflow monitoring using USER_LLM event type."""
        
        # 1) Record user query -> user_llm (input)
        query_result = self.check_with_aiceberg(user_message, "standard_query")
        if query_result.get("event_result", "passed") == "rejected":
            return self.valves.block_message
        query_event_id = query_result.get("event_id")

        # 2) Prepare the payload for the LLM
        payload = {**body, "model": self.valves.target_model}
        payload.pop("user", None)
        payload.pop("chat_id", None)
        payload.pop("title", None)

        # 3) Call the LLM
        openai_response = self._call_openai(payload, body)
        if openai_response.startswith("Error:"):
            return openai_response

        # 4) Record LLM response -> user_llm (output)
        if query_event_id:
            self.check_with_aiceberg(
                content=openai_response,
                phase="standard_response",
                event_id=query_event_id,
            )

        return openai_response

    def _call_openai(self, payload: dict, body: dict) -> str:
        """Call OpenAI API and handle streaming/non-streaming responses."""
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
                        data = line[6:].trip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                content_parts.append(delta)
                        except Exception:
                            pass
                return "".join(content_parts)
            else:
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            print(f"OpenAI error: {exc}")
            return f"Error: {str(exc)}"