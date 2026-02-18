"""
Core Agent Loop
Think → Act → Observe cycle with MQTT integration,
voice approval gates, and context compression via Jetson summarizer.
"""

import re
import json
import time
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable

from .state import TaskStatus, TaskContext, Observation
from .tools import Tool
from .config import AgentConfig


class Agent:
    """
    Generic autonomous agent with think→act→observe loop.

    Usage:
        agent = Agent(config, tools, mqtt_client, brain_fn)
        result = await agent.run("Build a rent tracker app")
    """

    def __init__(
        self,
        config: AgentConfig,
        tools: Dict[str, Tool],
        mqtt_client,
        brain_fn: Callable[[list], Awaitable[str]],
    ):
        self.config = config
        self.tools = tools
        self.mqtt = mqtt_client
        self.brain = brain_fn
        self.context = TaskContext(goal=config.goal)
        self.topic = config.mqtt_topic_prefix or f"sage/agent/{config.name}"
        self._running = False
        self._approval_futures: Dict[str, asyncio.Future] = {}

    # --- Public API ---

    async def run(self, goal: str = None) -> TaskContext:
        """Main agent loop."""
        if goal:
            self.context.goal = goal
        self.context.status = TaskStatus.RUNNING
        self._running = True
        self._publish_status("running", goal=self.context.goal)
        print(f"[Agent:{self.config.name}] Started — goal: {self.context.goal}")

        iteration = 0
        while self._running and iteration < self.config.max_iterations:
            iteration += 1

            # THINK
            try:
                action = await self._think()
            except Exception as e:
                print(f"[Agent:{self.config.name}] Think error: {e}")
                self.context.observations.append(
                    Observation(tool="_think", params={}, result=f"Error: {e}")
                )
                continue

            print(f"[Agent:{self.config.name}] Action: {action.get('type')} "
                  f"tool={action.get('tool', 'n/a')}")

            # COMPLETE
            if action.get("type") == "complete":
                self.context.status = TaskStatus.COMPLETED
                self.context.completed_at = time.time()
                summary = action.get("summary", "Task completed")
                self._publish_status("completed", summary=summary)
                print(f"[Agent:{self.config.name}] Completed: {summary}")
                break

            # ASK USER
            if action.get("type") == "ask_user":
                self.context.status = TaskStatus.WAITING_INPUT
                response = await self._ask_user(action.get("message", ""))
                self.context.status = TaskStatus.RUNNING
                self.context.observations.append(
                    Observation(
                        tool="ask_user",
                        params={"message": action["message"]},
                        result=response,
                    )
                )
                continue

            # TOOL EXECUTION
            tool_name = action.get("tool", "")
            tool = self.tools.get(tool_name)
            if not tool:
                self.context.observations.append(
                    Observation(
                        tool=tool_name,
                        params={},
                        result=f"Error: unknown tool '{tool_name}'",
                    )
                )
                continue

            # Approval gate
            if tool.needs_approval:
                self.context.status = TaskStatus.WAITING_APPROVAL
                reason = action.get("reason", f"Run {tool.name}")
                approved = await self._ask_user(
                    f"Agent wants to {reason}. Go ahead?"
                )
                self.context.status = TaskStatus.RUNNING
                if self._is_rejection(approved):
                    self.context.observations.append(
                        Observation(
                            tool=tool.name,
                            params=action.get("params", {}),
                            result="User rejected",
                        )
                    )
                    continue

            # ACT
            params = action.get("params", {})
            try:
                result = await tool.fn(**params)
            except Exception as e:
                result = f"Error: {e}"

            # OBSERVE
            self.context.observations.append(
                Observation(tool=tool.name, params=params, result=result)
            )
            self.context.raw_turns += 1
            self._publish_status(
                "progress", iteration=iteration, last_tool=tool.name
            )

            # COMPRESS context if needed
            if self.context.raw_turns >= self.config.compress_after:
                await self._compress_context()

        # Max iterations safety
        if self._running and iteration >= self.config.max_iterations:
            self.context.status = TaskStatus.FAILED
            self._publish_status("failed", reason="max_iterations reached")
            print(f"[Agent:{self.config.name}] Failed: max iterations ({self.config.max_iterations})")

        return self.context

    def stop(self):
        """Stop the agent loop gracefully."""
        self._running = False
        print(f"[Agent:{self.config.name}] Stop requested")

    def receive_approval(self, response: str):
        """Called externally when user responds to an approval request."""
        for key, future in list(self._approval_futures.items()):
            if not future.done():
                future.set_result(response)
                break

    # --- Internal ---

    async def _think(self) -> Dict[str, Any]:
        """Ask the brain LLM what to do next."""
        messages = self._build_prompt()
        response = await self.brain(messages)
        return self._parse_action(response)

    def _build_prompt(self) -> list:
        """Construct LLM messages from current state."""
        tool_lines = []
        for t in self.tools.values():
            param_str = ", ".join(f"{k}: {v}" for k, v in t.parameters.items())
            approval = " [NEEDS APPROVAL]" if t.needs_approval else ""
            tool_lines.append(f"- {t.name}({param_str}): {t.description}{approval}")
        tool_block = "\n".join(tool_lines)

        # Context: summary + recent raw observations
        if self.context.summary:
            context_text = f"Context summary:\n{self.context.summary}\n\nRecent:\n"
            recent = self.context.observations[-3:]
        else:
            context_text = "Observations:\n"
            recent = self.context.observations[-10:]

        if not recent:
            context_text = "No observations yet. This is the first step."
        else:
            for obs in recent:
                result_str = str(obs.result)[:500]
                context_text += f"[{obs.tool}] {result_str}\n"

        system = (
            f"You are '{self.config.name}', an autonomous agent.\n"
            f"Goal: {self.context.goal}\n\n"
            f"Available tools:\n{tool_block}\n\n"
            "Respond with a single JSON object (no markdown, no extra text):\n"
            'To use a tool: {"type": "tool", "tool": "name", "params": {...}, "reason": "why"}\n'
            'To ask the user: {"type": "ask_user", "message": "your question"}\n'
            'To finish: {"type": "complete", "summary": "what was accomplished"}\n\n'
            "Rules:\n"
            "- One action per response\n"
            "- Always include 'reason' when using a tool\n"
            "- Use ask_user only when you genuinely need human input\n"
            "- Complete when the goal is achieved or cannot be achieved\n"
        )

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": context_text},
        ]

    def _parse_action(self, response: str) -> Dict[str, Any]:
        """Extract JSON action from LLM response."""
        # Try to find JSON in the response
        # Handle markdown code blocks
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (```json and ```)
            json_lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(json_lines).strip()

        # Try direct parse
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass

        # Try to find JSON object in the text
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: treat entire response as completion
        print(f"[Agent:{self.config.name}] Could not parse action, treating as complete")
        return {"type": "complete", "summary": response[:500]}

    async def _ask_user(self, message: str) -> str:
        """Ask user via Sage voice and wait for response."""
        # Publish the question
        payload = {
            "agent": self.config.name,
            "message": message,
            "task_id": self.context.task_id,
        }
        self.mqtt.publish(
            f"{self.topic}/needs_approval", json.dumps(payload)
        )
        # Also speak it via TTS
        self.mqtt.publish(
            "sage/voice/response",
            json.dumps({"text": message, "source": "agent", "agent": self.config.name}),
        )

        # Wait for response
        response = await self._wait_for_mqtt(
            f"{self.topic}/approval_response", timeout=120
        )
        if not response:
            return "No response (timed out)"
        return response

    async def _compress_context(self):
        """Send observations to Jetson summarizer via MQTT."""
        obs_text = "\n".join(
            f"[{o.tool}]: {str(o.result)[:200]}"
            for o in self.context.observations
        )
        payload = {
            "text": obs_text,
            "task_id": self.context.task_id,
            "goal": self.context.goal,
        }
        self.mqtt.publish("sage/memory/summarize", json.dumps(payload))
        print(f"[Agent:{self.config.name}] Requesting context compression...")

        summary = await self._wait_for_mqtt(
            f"sage/memory/summary/{self.context.task_id}", timeout=30
        )
        if summary:
            self.context.summary = summary
            self.context.observations = self.context.observations[-3:]
            self.context.raw_turns = 0
            print(f"[Agent:{self.config.name}] Context compressed: {len(summary)} chars")
        else:
            # Fallback: self-compress by truncating old observations
            print(f"[Agent:{self.config.name}] Summarizer unavailable, self-compressing")
            if len(self.context.observations) > 5:
                kept = self.context.observations[-5:]
                discarded_text = "\n".join(
                    f"[{o.tool}]: {str(o.result)[:100]}"
                    for o in self.context.observations[:-5]
                )
                self.context.summary = (
                    (self.context.summary + "\n" if self.context.summary else "")
                    + f"Previous actions: {discarded_text}"
                )[:1500]
                self.context.observations = kept
                self.context.raw_turns = 0

    async def _wait_for_mqtt(self, topic: str, timeout: float = 120) -> str:
        """Wait for a message on an MQTT topic."""
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        def on_msg(client, userdata, msg):
            if not future.done():
                try:
                    data = json.loads(msg.payload.decode())
                    result = data.get("text", data.get("response", str(data)))
                except (json.JSONDecodeError, ValueError):
                    result = msg.payload.decode()
                loop.call_soon_threadsafe(future.set_result, result)

        self.mqtt.subscribe(topic)
        self.mqtt.message_callback_add(topic, on_msg)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return ""
        finally:
            self.mqtt.message_callback_remove(topic)
            self.mqtt.unsubscribe(topic)

    @staticmethod
    def _is_rejection(response: str) -> bool:
        """Check if user response is a rejection."""
        lower = response.lower().strip()
        rejections = {"no", "nah", "nope", "stop", "cancel", "don't", "dont", "hapana"}
        return any(r in lower for r in rejections)

    def _publish_status(self, status: str, **extra):
        payload = {
            "status": status,
            "task_id": self.context.task_id,
            "agent": self.config.name,
            "timestamp": time.time(),
            **extra,
        }
        self.mqtt.publish(f"{self.topic}/status", json.dumps(payload))
