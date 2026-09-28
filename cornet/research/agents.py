"""Cursor SDK agent creation. Cloud options are never constructed."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from cornet.research.tools import TOOL_NAMES, ToolDef

FORBIDDEN_TOOLS = frozenset({"shell", "edit", "task"})


def tool_allowlist(*, allow_web_search: bool) -> list[str]:
    tools = ["mcp"]
    if allow_web_search:
        tools.append("webSearch")
    if FORBIDDEN_TOOLS.intersection(tools):
        raise RuntimeError("shell, edit and task must not be offered")
    return tools


def local_options(cwd: Path, custom_tools: dict[str, Any], *, allow_web_search: bool) -> dict[str, Any]:
    options = {
        "local": {
            "cwd": str(cwd),
            "custom_tools": custom_tools,
            "setting_sources": [],
        },
        "tools": tool_allowlist(allow_web_search=allow_web_search),
    }
    if "cloud" in options:
        raise RuntimeError("cloud options are not used")
    names = set(custom_tools)
    if names != set(TOOL_NAMES):
        raise RuntimeError(f"custom tools must be exactly {TOOL_NAMES}")
    return options


def assert_known_model(model: str, available: list[str]) -> None:
    if model not in available:
        raise SystemExit(f"unknown model {model}; available: {', '.join(available)}")


def sdk_custom_tools(tools: dict[str, ToolDef]) -> dict[str, Any]:
    from cursor_sdk import CustomTool

    return {
        name: CustomTool(
            description=tool.description,
            input_schema=tool.input_schema,
            execute=lambda args, _context, fn=tool.execute: fn(args),
        )
        for name, tool in tools.items()
    }


def create_local_agent(
    *,
    api_key: str,
    model: str,
    cwd: Path,
    custom_tools: dict[str, Any],
    allow_web_search: bool,
    available_models: list[str],
    resume_id: str | None = None,
):
    assert_known_model(model, available_models)
    options = local_options(cwd, custom_tools, allow_web_search=allow_web_search)
    from cursor_sdk import Agent, AgentOptions, LocalAgentOptions

    local = LocalAgentOptions(
        cwd=options["local"]["cwd"],
        custom_tools=options["local"]["custom_tools"],
        setting_sources=[],
    )
    if resume_id:
        return Agent.resume(
            resume_id,
            AgentOptions(
                api_key=api_key,
                model=model,
                local=local,
            ),
        )
    return Agent.create(
        AgentOptions(
            api_key=api_key,
            model=model,
            local=local,
        ),
    )


def send_with_retry(agent: Any, prompt: str, log: Callable[[str | None, str | None], None]) -> Any:
    """Retry startup failures. A run status of error is returned, not retried."""
    delay = 1.0
    while True:
        try:
            run = agent.send(prompt)
            log(getattr(agent, "agent_id", None), getattr(run, "id", None))
            result = run.wait() if hasattr(run, "wait") else run
            return result
        except Exception as exc:
            if type(exc).__name__ != "CursorAgentError":
                raise
            if not getattr(exc, "is_retryable", False):
                raise
            time.sleep(_retry_seconds(getattr(exc, "retry_after", None), delay))
            delay *= 2


def _retry_seconds(retry_after: str | None, fallback: float) -> float:
    if not retry_after:
        return fallback
    try:
        return max(float(retry_after), 0.0)
    except ValueError:
        return fallback
