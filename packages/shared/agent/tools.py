"""
Agent Tool Definitions
Tools are callable actions an agent can invoke during its think→act→observe loop.
"""

from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any, Dict


@dataclass
class Tool:
    """A tool available to an agent."""
    name: str
    description: str
    fn: Callable[..., Awaitable[Any]]
    needs_approval: bool = False
    parameters: Dict[str, str] = field(default_factory=dict)

    def to_schema(self) -> Dict[str, Any]:
        """Serialize for LLM prompts and YAML agent configs."""
        return {
            "name": self.name,
            "description": self.description,
            "needs_approval": self.needs_approval,
            "parameters": self.parameters,
        }


# --- Built-in tool factory functions ---
# These create Tool instances wired to Sage's existing services.
# Called during agent initialization with live MQTT client and brain references.


def make_ask_user_tool(mqtt_client, topic_prefix: str) -> Tool:
    """Tool that asks the user a question via Sage voice and waits for response."""

    async def ask_user(message: str) -> str:
        import json
        mqtt_client.publish(
            "sage/voice/response",
            json.dumps({"text": message, "source": "agent", "no_tts": False}),
        )
        # Actual waiting is handled by the Agent._ask_user method
        return "Question sent to user via voice"

    return Tool(
        name="ask_user",
        description="Ask the user a question via Sage voice. Use for clarification or decisions.",
        fn=ask_user,
        parameters={"message": "The question to ask the user"},
    )


def make_report_status_tool(mqtt_client) -> Tool:
    """Tool that speaks a status update (fire-and-forget, no wait)."""

    async def report_status(message: str) -> str:
        import json
        mqtt_client.publish(
            "sage/voice/response",
            json.dumps({"text": message, "source": "agent", "no_tts": False}),
        )
        return "Status reported to user"

    return Tool(
        name="report_status",
        description="Speak a status update to the user. Fire-and-forget, does not wait for response.",
        fn=report_status,
        parameters={"message": "Status message to speak"},
    )


def make_call_llm_tool(brain_fn) -> Tool:
    """Tool that queries an LLM (local or cloud) for reasoning."""

    async def call_llm(prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        return await brain_fn(messages)

    return Tool(
        name="call_llm",
        description="Query an LLM for reasoning, analysis, or text generation. Use for tasks that need thinking.",
        fn=call_llm,
        parameters={"prompt": "The prompt to send to the LLM"},
    )


def make_architect_plan_tool(architect_bridge) -> Tool:
    """Tool that creates an implementation plan via the Architect."""

    async def architect_plan(query: str, project_id: str = "sage_brain") -> Dict:
        result = await architect_bridge.dispatch(
            project_id=project_id,
            query=query,
            task_type="plan",
        )
        return result

    return Tool(
        name="architect_plan",
        description="Create an implementation plan for a code task. Returns plan status and summary.",
        fn=architect_plan,
        parameters={
            "query": "What to plan (e.g. 'Add expense tracking')",
            "project_id": "Target project (default: sage_brain)",
        },
    )


def make_architect_build_tool(architect_bridge) -> Tool:
    """Tool that builds code from an existing plan via the Architect."""

    async def architect_build(query: str, project_id: str = "sage_brain") -> Dict:
        result = await architect_bridge.dispatch(
            project_id=project_id,
            query=query,
            task_type="code",
        )
        return result

    return Tool(
        name="architect_build",
        description="Build code from a plan. Generates files, runs tests, auto-fixes failures.",
        fn=architect_build,
        needs_approval=True,
        parameters={
            "query": "What to build",
            "project_id": "Target project (default: sage_brain)",
        },
    )


def make_run_tests_tool() -> Tool:
    """Tool that runs a test suite."""

    async def run_tests(path: str = ".", command: str = "python -m pytest") -> str:
        import asyncio
        proc = await asyncio.create_subprocess_shell(
            f"cd {path} && {command}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode()[-2000:]  # Last 2000 chars
        status = "PASSED" if proc.returncode == 0 else "FAILED"
        return f"{status}\n{output}"

    return Tool(
        name="run_tests",
        description="Run a test suite. Returns PASSED or FAILED with output.",
        fn=run_tests,
        parameters={
            "path": "Directory to run tests in (default: current dir)",
            "command": "Test command (default: python -m pytest)",
        },
    )


def make_read_file_tool() -> Tool:
    """Tool that reads a file's contents."""

    async def read_file(path: str) -> str:
        try:
            with open(path, "r") as f:
                content = f.read()
            if len(content) > 5000:
                return content[:5000] + f"\n... (truncated, {len(content)} total chars)"
            return content
        except Exception as e:
            return f"Error reading {path}: {e}"

    return Tool(
        name="read_file",
        description="Read the contents of a file. Truncates large files to 5000 chars.",
        fn=read_file,
        parameters={"path": "Path to the file to read"},
    )


def make_write_file_tool() -> Tool:
    """Tool that writes content to a file."""

    async def write_file(path: str, content: str) -> str:
        import os
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return f"Written {len(content)} chars to {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"

    return Tool(
        name="write_file",
        description="Write content to a file. Creates directories if needed.",
        fn=write_file,
        needs_approval=True,
        parameters={
            "path": "Path to write to",
            "content": "Content to write",
        },
    )


def make_web_search_tool() -> Tool:
    """Tool that searches the web (requires search API key)."""

    async def web_search(query: str) -> str:
        import os
        import aiohttp

        api_key = os.getenv("SERPER_API_KEY") or os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Error: No search API key configured (SERPER_API_KEY or TAVILY_API_KEY)"

        # Try Serper first
        if os.getenv("SERPER_API_KEY"):
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                    json={"q": query, "num": 5},
                ) as resp:
                    data = await resp.json()
                    results = data.get("organic", [])
                    return "\n".join(
                        f"- {r.get('title', '')}: {r.get('snippet', '')} ({r.get('link', '')})"
                        for r in results[:5]
                    )

        return "Search API not configured"

    return Tool(
        name="web_search",
        description="Search the web for information. Returns top 5 results with snippets.",
        fn=web_search,
        parameters={"query": "Search query"},
    )


def make_deploy_tool() -> Tool:
    """Tool that deploys to Vercel."""

    async def deploy(project_path: str, provider: str = "vercel") -> str:
        import asyncio
        if provider == "vercel":
            cmd = f"cd {project_path} && vercel --prod --yes"
        else:
            return f"Unknown deploy provider: {provider}"

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode()[-2000:]
        status = "SUCCESS" if proc.returncode == 0 else "FAILED"
        return f"Deploy {status}\n{output}"

    return Tool(
        name="deploy",
        description="Deploy a project to production (Vercel). Requires approval.",
        fn=deploy,
        needs_approval=True,
        parameters={
            "project_path": "Path to the project to deploy",
            "provider": "Deploy provider (default: vercel)",
        },
    )


def make_write_agent_config_tool(config_dir: str = "agents") -> Tool:
    """Tool for self-spawning: creates a new agent YAML config."""

    async def write_agent_config(
        name: str,
        goal: str,
        tools: str = "",
        model: str = "local",
        max_iterations: int = 50,
        schedule: str = "",
        budget_limit_usd: float = 5.0,
    ) -> str:
        import os
        import yaml

        config = {
            "name": name,
            "goal": goal,
            "tools": [t.strip() for t in tools.split(",") if t.strip()] if tools else [],
            "model": model,
            "max_iterations": max_iterations,
            "budget_limit_usd": budget_limit_usd,
            "needs_approval_to_start": True,
            "compress_after": 8,
        }
        if schedule:
            config["schedule"] = schedule

        os.makedirs(config_dir, exist_ok=True)
        path = os.path.join(config_dir, f"{name}.yaml")
        with open(path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        return f"Agent config written to {path}"

    return Tool(
        name="write_agent_config",
        description="Create a new agent definition YAML file. For self-spawning new agents.",
        fn=write_agent_config,
        needs_approval=True,
        parameters={
            "name": "Agent name (lowercase, underscores)",
            "goal": "What this agent should do",
            "tools": "Comma-separated tool names this agent needs",
            "model": "LLM to use: 'local' or 'cloud' (default: local)",
            "max_iterations": "Max loop iterations (default: 50)",
            "schedule": "Cron expression for recurring (optional, e.g. '0 8 * * 1')",
            "budget_limit_usd": "Max cloud spend in USD (default: 5.0)",
        },
    )


def make_register_agent_tool(registry) -> Tool:
    """Tool that loads an agent config into the live registry."""

    async def register_agent(config_path: str) -> str:
        from .config import AgentConfig
        try:
            config = AgentConfig.from_yaml(config_path)
            registry.register_config(config)
            return f"Agent '{config.name}' registered and available"
        except Exception as e:
            return f"Error registering agent: {e}"

    return Tool(
        name="register_agent",
        description="Load an agent config YAML into the live registry so it can be started.",
        fn=register_agent,
        parameters={"config_path": "Path to the agent YAML config file"},
    )
