"""
Agent Bridge
Allows Brain to start, stop, query, and manage agents via voice commands.

Follows the same pattern as architect_bridge.py:
- Lazy initialization
- Async dispatch
- MQTT integration for agent communication
"""

import sys
import os
import re
import asyncio
import json
from typing import Dict, Any, Optional, Callable, Awaitable

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class AgentBridge:
    """
    Bridge between Brain voice handler and the Agent framework.
    Handles voice commands related to agent lifecycle.
    """

    def __init__(self, mqtt_client=None):
        self._registry = None
        self._mqtt = mqtt_client
        self._brain_fn = None
        self._architect_bridge = None

    def initialize(
        self,
        mqtt_client,
        brain_fn: Callable[[list], Awaitable[str]],
        architect_bridge=None,
    ):
        """Wire up with live references. Called once during brain startup."""
        self._mqtt = mqtt_client
        self._brain_fn = brain_fn
        self._architect_bridge = architect_bridge

        from shared.agent.registry import AgentRegistry
        from shared.agent.config import AgentConfig
        from shared.agent import tools as agent_tools

        self._registry = AgentRegistry.get(config_dir=os.path.join(REPO_ROOT, "agents"))

        def tool_factory(config: AgentConfig) -> Dict:
            """Build tools dict for an agent based on its config."""
            available = {}

            # Always-available tools
            available["report_status"] = agent_tools.make_report_status_tool(mqtt_client)
            available["call_llm"] = agent_tools.make_call_llm_tool(brain_fn)
            available["read_file"] = agent_tools.make_read_file_tool()
            available["write_file"] = agent_tools.make_write_file_tool()
            available["run_tests"] = agent_tools.make_run_tests_tool()
            available["web_search"] = agent_tools.make_web_search_tool()

            # Architect tools (if architect bridge available)
            if architect_bridge:
                available["architect_plan"] = agent_tools.make_architect_plan_tool(architect_bridge)
                available["architect_build"] = agent_tools.make_architect_build_tool(architect_bridge)

            # Self-spawning tools
            available["write_agent_config"] = agent_tools.make_write_agent_config_tool(
                os.path.join(REPO_ROOT, "agents")
            )
            available["register_agent"] = agent_tools.make_register_agent_tool(self._registry)

            # Deploy tool
            available["deploy"] = agent_tools.make_deploy_tool()

            # Filter to only tools this agent config requests (if specified)
            if config.tools:
                return {k: v for k, v in available.items() if k in config.tools}
            return available

        self._registry.initialize(
            mqtt_client=mqtt_client,
            brain_fn=brain_fn,
            tool_factory=tool_factory,
        )

        print(f"[AgentBridge] Initialized. Available configs: {list(self._registry.configs.keys())}")

    async def dispatch(self, query: str) -> Dict[str, Any]:
        """
        Handle an agent-related voice command.

        Parses the query to determine the action:
        - start/run/launch → start an agent
        - stop/pause/kill → stop an agent
        - status/report → get agent status
        - build/create agent → spawn a new agent definition
        - list agents → list available and running agents
        """
        if not self._registry:
            return {
                "type": "error",
                "text": "Agent system not initialized.",
                "intent": "agent_task",
            }

        lower = query.lower().strip()
        action = self._parse_action(lower)
        print(f"[AgentBridge] Action: {action['action']}, target: {action.get('target', 'n/a')}")

        if action["action"] == "start":
            return await self._handle_start(action, query)
        elif action["action"] == "stop":
            return await self._handle_stop(action)
        elif action["action"] == "status":
            return await self._handle_status()
        elif action["action"] == "list":
            return await self._handle_list()
        elif action["action"] == "create":
            return await self._handle_create(query)
        else:
            return {
                "type": "acknowledged",
                "text": f"I heard an agent command but I'm not sure what to do. Try 'start agent', 'agent status', or 'list agents'.",
                "intent": "agent_task",
            }

    def _parse_action(self, text: str) -> Dict[str, str]:
        """Parse voice command into action + target."""
        # Start/run/launch
        if re.search(r'\b(start|run|launch|spin up|kick off)\b', text):
            target = self._extract_agent_name(text)
            return {"action": "start", "target": target}

        # Stop/pause/kill
        if re.search(r'\b(stop|pause|kill|cancel)\b', text):
            target = self._extract_agent_name(text)
            return {"action": "stop", "target": target}

        # Status/report
        if re.search(r'\b(status|report|update|how.{0,10}doing|progress)\b', text):
            return {"action": "status"}

        # List
        if re.search(r'\b(list|show|what agents)\b', text):
            return {"action": "list"}

        # Create/build agent
        if re.search(r'\b(build|create|make)\s+me\s+(an?\s+)?agent\b', text):
            return {"action": "create"}

        return {"action": "unknown"}

    def _extract_agent_name(self, text: str) -> Optional[str]:
        """Try to extract an agent name from the command."""
        # "start the research agent" → "research"
        # "run factory pipeline" → "factory"
        # "launch research_agent" → "research_agent"
        patterns = [
            r'\b(?:start|run|launch|stop|pause|kill)\s+(?:the\s+)?(\w+)\s+agent\b',
            r'\b(?:start|run|launch|stop|pause|kill)\s+(?:the\s+)?(\w+)\s+pipeline\b',
            r'\b(?:start|run|launch|stop|pause|kill)\s+(?:the\s+)?(\w+_\w+)\b',
            r'\bagent\s+(\w+)\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).lower()
                if name not in ("the", "a", "an", "my", "this", "that", "me"):
                    return name
        return None

    async def _handle_start(self, action: Dict, original_query: str) -> Dict:
        """Start an agent."""
        target = action.get("target")

        if target and target in self._registry.configs:
            agent = await self._registry.start_agent(target)
            if agent:
                return {
                    "type": "acknowledged",
                    "text": f"Started the {target} agent. I'll keep you posted on progress.",
                    "intent": "agent_task",
                    "task_id": agent.context.task_id,
                }
            return {
                "type": "error",
                "text": f"Failed to start the {target} agent.",
                "intent": "agent_task",
            }

        # No specific agent named — list available ones
        available = list(self._registry.configs.keys())
        if available:
            names = ", ".join(available)
            return {
                "type": "acknowledged",
                "text": f"Which agent? Available: {names}",
                "intent": "agent_task",
            }
        return {
            "type": "acknowledged",
            "text": "No agents configured yet. Say 'build me an agent' to create one.",
            "intent": "agent_task",
        }

    async def _handle_stop(self, action: Dict) -> Dict:
        """Stop a running agent."""
        target = action.get("target")
        if not target:
            return {
                "type": "acknowledged",
                "text": "Which agent should I stop?",
                "intent": "agent_task",
            }

        # Find by name in running agents
        for task_id, agent in self._registry.running.items():
            if agent.config.name == target:
                self._registry.stop_agent(task_id)
                return {
                    "type": "acknowledged",
                    "text": f"Stopped the {target} agent.",
                    "intent": "agent_task",
                }

        return {
            "type": "acknowledged",
            "text": f"No running agent named '{target}'.",
            "intent": "agent_task",
        }

    async def _handle_status(self) -> Dict:
        """Get status of all agents."""
        summary = self._registry.get_status_summary()
        return {
            "type": "success",
            "text": summary,
            "intent": "agent_task",
        }

    async def _handle_list(self) -> Dict:
        """List available and running agents."""
        status = self._registry.get_status()
        configs = status["available_configs"]
        running = status["running_agents"]

        parts = []
        if configs:
            parts.append(f"Available agents: {', '.join(configs)}")
        else:
            parts.append("No agents configured yet.")

        active_count = len([r for r in running.values() if r["status"] in ("running", "waiting_approval")])
        if active_count:
            parts.append(f"{active_count} currently running.")
        else:
            parts.append("None running right now.")

        return {
            "type": "success",
            "text": " ".join(parts),
            "intent": "agent_task",
        }

    async def _handle_create(self, query: str) -> Dict:
        """Create a new agent via the meta-builder agent."""
        # Check if we have a builder_agent config
        if "builder_agent" in self._registry.configs:
            agent = await self._registry.start_agent(
                "builder_agent",
                goal=f"Create a new agent based on this request: {query}",
            )
            if agent:
                return {
                    "type": "acknowledged",
                    "text": "I'm working on creating that agent for you. I'll let you know when it's ready.",
                    "intent": "agent_task",
                    "task_id": agent.context.task_id,
                }

        # Fallback: no builder agent, create a basic config directly
        # Extract what the user wants from the query
        return {
            "type": "acknowledged",
            "text": "I'll need a builder agent for that. Let me create one first. What should this new agent do?",
            "intent": "agent_task",
        }

    def route_approval(self, agent_name: str, response: str) -> bool:
        """Route a voice approval response to the waiting agent."""
        if self._registry:
            return self._registry.route_approval(agent_name, response)
        return False

    def shutdown(self):
        """Stop all running agents."""
        if self._registry:
            for task_id in list(self._registry.running.keys()):
                self._registry.stop_agent(task_id)
