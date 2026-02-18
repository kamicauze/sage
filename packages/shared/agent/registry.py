"""
Agent Registry
Singleton that tracks available agent configs and running agent instances.
Loads YAML configs from the agents/ directory and manages agent lifecycle.
"""

import os
import asyncio
import time
import json
from typing import Dict, Optional, Callable, Awaitable

from .config import AgentConfig
from .base import Agent
from .tools import Tool
from .state import TaskStatus


class AgentRegistry:
    """Singleton registry of agent configs and running instances."""

    _instance: Optional["AgentRegistry"] = None

    def __init__(self, config_dir: str = "agents"):
        self.configs: Dict[str, AgentConfig] = {}
        self.running: Dict[str, Agent] = {}  # task_id → Agent
        self._config_dir = config_dir
        self._mqtt = None
        self._brain_fn = None
        self._tool_factory = None

    @classmethod
    def get(cls, config_dir: str = "agents") -> "AgentRegistry":
        if cls._instance is None:
            cls._instance = cls(config_dir)
        return cls._instance

    def initialize(
        self,
        mqtt_client,
        brain_fn: Callable[[list], Awaitable[str]],
        tool_factory: Callable[[AgentConfig], Dict[str, Tool]],
    ):
        """Wire up the registry with live MQTT and brain references."""
        self._mqtt = mqtt_client
        self._brain_fn = brain_fn
        self._tool_factory = tool_factory
        self.load_configs()

    # --- Config Management ---

    def register_config(self, config: AgentConfig):
        self.configs[config.name] = config
        print(f"[AgentRegistry] Registered config: {config.name}")

    def load_configs(self):
        """Load all YAML agent configs from the config directory."""
        if not os.path.isdir(self._config_dir):
            print(f"[AgentRegistry] No config directory: {self._config_dir}")
            return

        count = 0
        for filename in os.listdir(self._config_dir):
            if filename.endswith((".yaml", ".yml", ".json")):
                path = os.path.join(self._config_dir, filename)
                try:
                    config = AgentConfig.from_yaml(path)
                    self.configs[config.name] = config
                    count += 1
                except Exception as e:
                    print(f"[AgentRegistry] Failed to load {path}: {e}")

        print(f"[AgentRegistry] Loaded {count} agent configs from {self._config_dir}/")

    # --- Agent Lifecycle ---

    async def start_agent(
        self,
        config_name: str,
        goal: str = None,
        tools_override: Dict[str, Tool] = None,
    ) -> Optional[Agent]:
        """Start an agent from a registered config."""
        config = self.configs.get(config_name)
        if not config:
            print(f"[AgentRegistry] Unknown agent config: {config_name}")
            return None

        if not self._mqtt or not self._brain_fn:
            print("[AgentRegistry] Not initialized — call initialize() first")
            return None

        # Build tools for this agent
        if tools_override:
            tools = tools_override
        elif self._tool_factory:
            tools = self._tool_factory(config)
        else:
            tools = {}

        # Create agent
        agent = Agent(
            config=config,
            tools=tools,
            mqtt_client=self._mqtt,
            brain_fn=self._brain_fn,
        )

        effective_goal = goal or config.goal
        self.running[agent.context.task_id] = agent

        # Publish registry status
        self._publish_registry_status()

        # Run in background task
        asyncio.ensure_future(self._run_and_cleanup(agent, effective_goal))

        print(f"[AgentRegistry] Started agent '{config_name}' — task_id={agent.context.task_id}")
        return agent

    async def _run_and_cleanup(self, agent: Agent, goal: str):
        """Run agent and clean up when done."""
        try:
            await agent.run(goal)
        except Exception as e:
            print(f"[AgentRegistry] Agent '{agent.config.name}' crashed: {e}")
            agent.context.status = TaskStatus.FAILED
        finally:
            self._publish_registry_status()

    def stop_agent(self, task_id: str) -> bool:
        """Stop a running agent by task_id."""
        agent = self.running.get(task_id)
        if agent:
            agent.stop()
            print(f"[AgentRegistry] Stopped agent task_id={task_id}")
            return True
        print(f"[AgentRegistry] No running agent with task_id={task_id}")
        return False

    def get_agent(self, task_id: str) -> Optional[Agent]:
        return self.running.get(task_id)

    def route_approval(self, agent_name: str, response: str):
        """Route an approval response to the correct running agent."""
        for agent in self.running.values():
            if agent.config.name == agent_name and agent.context.status in (
                TaskStatus.WAITING_APPROVAL,
                TaskStatus.WAITING_INPUT,
            ):
                agent.receive_approval(response)
                return True
        return False

    # --- Status ---

    def get_status(self) -> Dict:
        """Get status of all agents (for Sage to report via voice)."""
        running = {}
        for task_id, agent in self.running.items():
            running[task_id] = {
                "name": agent.config.name,
                "status": agent.context.status.value,
                "goal": agent.context.goal[:100],
                "iterations": len(agent.context.observations),
                "elapsed_s": round(agent.context.elapsed_seconds(), 1),
            }

        return {
            "available_configs": list(self.configs.keys()),
            "running_agents": running,
            "total_running": len([
                a for a in self.running.values()
                if a.context.status in (TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL, TaskStatus.WAITING_INPUT)
            ]),
        }

    def get_status_summary(self) -> str:
        """Human-readable status summary for voice output."""
        status = self.get_status()
        active = status["total_running"]

        if active == 0:
            return "No agents running right now."

        lines = [f"{active} agent{'s' if active != 1 else ''} running:"]
        for info in status["running_agents"].values():
            if info["status"] in ("running", "waiting_approval", "waiting_input"):
                lines.append(
                    f"  {info['name']}: {info['status']} — {info['goal'][:60]}"
                )
        return "\n".join(lines)

    def _publish_registry_status(self):
        if self._mqtt:
            self._mqtt.publish(
                "sage/agent/registry/status",
                json.dumps(self.get_status()),
            )
