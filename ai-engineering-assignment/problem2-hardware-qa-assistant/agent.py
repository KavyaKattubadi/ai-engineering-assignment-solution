"""
LLM orchestration layer for the Hardware Q&A Assistant.

Supports:
- OpenAI-compatible APIs (including local Ollama with OpenAI endpoint)
- Strict tool-calling loop
- Session memory for multi-turn follow-ups
- Strong anti-hallucination instructions
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from tools import TOOL_DEFINITIONS, available_tools, execute_tool

SYSTEM_PROMPT = """You are a precise Linux hardware assistant running on the user's laptop.

RULES (must follow):
1. Answer ONLY from the JSON data returned by the tools.
2. If the required information is not present in the tool results, reply exactly:
   "I cannot determine this from the available system data."
3. Never invent, guess or extrapolate hardware specifications.
4. Prefer short, clear answers. Use numbers and units the user asked for.
5. For follow-up questions, reuse previously collected data when possible.
6. When a tool returns an "error" field, explain the limitation honestly (e.g. missing sudo for dmidecode).

You have access to the following tools. Call them when you need facts about the machine.
"""


class HardwareAgent:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        model: any OpenAI-compatible model name
        base_url: set to "http://localhost:11434/v1" for Ollama
        api_key: required for cloud; "ollama" is fine for local
        """
        self.model = model
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY") or "ollama",
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )

        # Only expose tools that actually exist on this machine
        self.tools = [
            t for t in TOOL_DEFINITIONS
            if t["function"]["name"] in available_tools()
        ]

        # Conversation + cached tool results for multi-turn
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.tool_cache: Dict[str, Any] = {}

    def ask(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})

        # First LLM call – may request tools
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=self.tools if self.tools else None,
            tool_choice="auto" if self.tools else None,
            temperature=0.1,
        )
        msg = response.choices[0].message

        # Tool-calling loop (max 4 rounds to avoid runaway)
        rounds = 0
        while msg.tool_calls and rounds < 4:
            rounds += 1
            self.messages.append(msg)  # assistant message with tool_calls

            for call in msg.tool_calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                # Re-use cache if we already ran this tool this session
                if name in self.tool_cache:
                    result = self.tool_cache[name]
                else:
                    result = execute_tool(name, **args)
                    self.tool_cache[name] = result

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

            # Next LLM turn with tool results
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=self.tools if self.tools else None,
                tool_choice="auto" if self.tools else None,
                temperature=0.1,
            )
            msg = response.choices[0].message

        # Final answer
        answer = msg.content or "I could not produce an answer."
        self.messages.append({"role": "assistant", "content": answer})
        return answer

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.tool_cache.clear()