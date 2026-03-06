"""
Agent Tool Definitions
Tools are callable actions an agent can invoke during its think→act→observe loop.
"""

from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any, Dict

from .policy import AgentToolPolicy
from .sandbox import ToolSandbox


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


def make_run_tests_tool(
    sandbox: ToolSandbox = None,
    policy: AgentToolPolicy = None,
) -> Tool:
    """Tool that runs a test suite."""
    policy = policy or AgentToolPolicy.from_env()
    sandbox = sandbox or ToolSandbox(policy)

    async def run_tests(path: str = ".", command: str = "python -m pytest") -> str:
        return await sandbox.run_command(command=command, cwd=path, max_output_chars=4000, timeout_sec=300)

    return Tool(
        name="run_tests",
        description="Run a test suite. Returns PASSED or FAILED with output.",
        fn=run_tests,
        parameters={
            "path": "Directory to run tests in (default: current dir)",
            "command": "Test command (default: python -m pytest)",
        },
    )


def make_read_file_tool(
    sandbox: ToolSandbox = None,
    policy: AgentToolPolicy = None,
) -> Tool:
    """Tool that reads a file's contents."""
    policy = policy or AgentToolPolicy.from_env()
    sandbox = sandbox or ToolSandbox(policy)

    async def read_file(path: str) -> str:
        try:
            return sandbox.read_text(path, max_chars=5000)
        except Exception as e:
            return f"Error reading {path}: {e}"

    return Tool(
        name="read_file",
        description="Read the contents of a file. Truncates large files to 5000 chars.",
        fn=read_file,
        parameters={"path": "Path to the file to read"},
    )


def make_write_file_tool(
    sandbox: ToolSandbox = None,
    policy: AgentToolPolicy = None,
) -> Tool:
    """Tool that writes content to a file."""
    policy = policy or AgentToolPolicy.from_env()
    sandbox = sandbox or ToolSandbox(policy)

    async def write_file(path: str, content: str) -> str:
        try:
            return sandbox.write_text(path, content)
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


def make_gmail_read_tool(api_base_url: str = "http://localhost:8000") -> Tool:
    """Tool that searches and reads Gmail messages."""

    async def gmail_read(query: str = "", max_results: int = 5) -> str:
        import requests as _requests
        url = f"{api_base_url}/google/gmail/messages"
        resp = _requests.get(url, params={"q": query, "max_results": max_results}, timeout=10)
        if not resp.ok:
            return f"Error listing messages: HTTP {resp.status_code}"
        messages = resp.json().get("messages", [])
        if not messages:
            return "No messages found."
        # Fetch details for top results
        summaries = []
        for msg in messages[:max_results]:
            msg_id = msg.get("id", "")
            detail_resp = _requests.get(f"{api_base_url}/google/gmail/messages/{msg_id}", params={"format": "metadata"}, timeout=10)
            if detail_resp.ok:
                payload = detail_resp.json().get("message", {})
                headers = {h["name"]: h["value"] for h in payload.get("payload", {}).get("headers", []) if h.get("name") in ("From", "Subject", "Date")}
                summaries.append(f"- [{msg_id}] {headers.get('Subject', '(no subject)')} from {headers.get('From', 'unknown')} ({headers.get('Date', '')})")
            else:
                summaries.append(f"- [{msg_id}] (could not fetch details)")
        return "Gmail messages:\n" + "\n".join(summaries)

    return Tool(
        name="gmail_read",
        description="Search and read Gmail messages. Returns subject, sender, and date for each match.",
        fn=gmail_read,
        parameters={
            "query": "Gmail search query (same syntax as Gmail search box). Empty = recent inbox.",
            "max_results": "Number of messages to return (default: 5)",
        },
    )


def make_gmail_send_tool(api_base_url: str = "http://localhost:8000") -> Tool:
    """Tool that sends an email via Gmail."""

    async def gmail_send(to: str, subject: str, body: str) -> str:
        import requests as _requests
        resp = _requests.post(
            f"{api_base_url}/google/gmail/send",
            json={"to": to, "subject": subject, "body": body},
            timeout=10,
        )
        if not resp.ok:
            return f"Error sending email: HTTP {resp.status_code}"
        msg_id = resp.json().get("message_id", "unknown")
        return f"Email sent to {to} (message id: {msg_id})"

    return Tool(
        name="gmail_send",
        description="Send an email via Gmail. Requires approval before sending.",
        fn=gmail_send,
        needs_approval=True,
        parameters={
            "to": "Recipient email address",
            "subject": "Email subject line",
            "body": "Email body text",
        },
    )


def make_gmail_archive_tool(api_base_url: str = "http://localhost:8000") -> Tool:
    """Tool that archives a Gmail message (removes INBOX label)."""

    async def gmail_archive(message_id: str) -> str:
        import requests as _requests
        resp = _requests.post(
            f"{api_base_url}/google/gmail/messages/{message_id}/modify",
            json={"remove_labels": ["INBOX"]},
            timeout=10,
        )
        if not resp.ok:
            return f"Error archiving message: HTTP {resp.status_code}"
        return f"Message {message_id} archived."

    return Tool(
        name="gmail_archive",
        description="Archive a Gmail message by removing it from the inbox. Requires approval.",
        fn=gmail_archive,
        needs_approval=True,
        parameters={"message_id": "The Gmail message ID to archive"},
    )


def make_browser_navigate_tool(session) -> Tool:
    """Tool that navigates to a URL in a browser session."""

    async def navigate(url: str) -> str:
        return await session.navigate(url)

    return Tool(
        name="browser_navigate",
        description="Navigate to a URL in a headless browser. Returns page title and status.",
        fn=navigate,
        needs_approval=True,
        parameters={"url": "The URL to navigate to"},
    )


def make_browser_click_tool(session) -> Tool:
    """Tool that clicks an element in the browser."""

    async def click(selector: str) -> str:
        return await session.click(selector)

    return Tool(
        name="browser_click",
        description="Click an element matching a CSS selector in the browser.",
        fn=click,
        needs_approval=True,
        parameters={"selector": "CSS selector of the element to click"},
    )


def make_browser_extract_tool(session) -> Tool:
    """Tool that extracts text content from the current page."""

    async def extract(selector: str = "body") -> str:
        return await session.extract(selector)

    return Tool(
        name="browser_extract",
        description="Extract text content from the current browser page using a CSS selector.",
        fn=extract,
        parameters={"selector": "CSS selector to extract text from (default: body)"},
    )


def make_browser_screenshot_tool(session) -> Tool:
    """Tool that takes a screenshot of the current browser page."""

    async def screenshot() -> str:
        return await session.screenshot()

    return Tool(
        name="browser_screenshot",
        description="Take a screenshot of the current browser page.",
        fn=screenshot,
        parameters={},
    )


def make_deploy_tool(
    sandbox: ToolSandbox = None,
    policy: AgentToolPolicy = None,
) -> Tool:
    """Tool that deploys to Vercel."""
    policy = policy or AgentToolPolicy.from_env()
    sandbox = sandbox or ToolSandbox(policy)

    async def deploy(project_path: str, provider: str = "vercel") -> str:
        if provider == "vercel":
            cmd = "vercel --prod --yes"
        else:
            return f"Unknown deploy provider: {provider}"

        output = await sandbox.run_command(
            command=cmd,
            cwd=project_path,
            max_output_chars=4000,
            timeout_sec=1200,
        )
        return f"Deploy result\n{output}"

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
        import yaml
        policy = AgentToolPolicy.from_env()

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

        path = f"{config_dir}/{name}.yaml"
        resolved = policy.resolve_write_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

        return f"Agent config written to {resolved}"

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
