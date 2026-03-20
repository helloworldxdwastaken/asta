"""MCP client manager — connects to configured MCP servers, discovers tools,
and routes tool calls.  Servers are defined in backend/mcp_servers.json."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "mcp_servers.json"

# ── Global state ──────────────────────────────────────────────────────
_sessions: dict[str, ClientSession] = {}
_contexts: dict[str, Any] = {}  # stdio context managers
_tasks: dict[str, asyncio.Task] = {}  # background tasks keeping servers alive
_tools: dict[str, dict] = {}  # tool_name -> {server, schema}
_ready_events: dict[str, asyncio.Event] = {}  # signals when a server is ready
_initialized = False
_lock = asyncio.Lock()


def _load_config() -> dict:
    """Load MCP server config from JSON."""
    if not CONFIG_PATH.exists():
        logger.warning("MCP config not found: %s", CONFIG_PATH)
        return {"servers": {}}
    return json.loads(CONFIG_PATH.read_text())


def _resolve_env(env_map: dict[str, str], db_keys: dict[str, str] | None = None) -> tuple[dict[str, str], list[str]]:
    """Resolve ${VAR} placeholders in env values from DB keys or os.environ."""
    resolved = {}
    missing = []
    for k, v in env_map.items():
        if v.startswith("${") and v.endswith("}"):
            var_name = v[2:-1]
            # Try DB keys first, then environment
            val = (db_keys or {}).get(var_name.lower(), "") or os.environ.get(var_name, "")
            if val:
                resolved[k] = val
            else:
                missing.append(var_name)
                logger.warning("MCP env var %s not found for %s", var_name, k)
        else:
            resolved[k] = v
    return resolved, missing


async def _run_server(
    name: str,
    config: dict,
    db_keys: dict[str, str] | None = None,
) -> None:
    """Start an MCP server inside a proper async context and keep it alive."""
    command = config["command"]
    args = config.get("args", [])
    env_map = config.get("env", {})

    # Resolve environment variables — skip if any required vars are missing
    resolved_env, missing = _resolve_env(env_map, db_keys)
    if missing:
        logger.warning("MCP server '%s' skipped — missing env vars: %s", name, missing)
        evt = _ready_events.get(name)
        if evt:
            evt.set()
        return

    env = {**os.environ, **resolved_env}

    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=env,
    )

    try:
        async with stdio_client(server_params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                _sessions[name] = session
                logger.info("MCP server '%s' started successfully", name)

                # Discover tools
                try:
                    result = await session.list_tools()
                    for tool in result.tools:
                        tool_name = f"mcp_{name}_{tool.name}"
                        _tools[tool_name] = {
                            "server": name,
                            "original_name": tool.name,
                            "description": tool.description or "",
                            "schema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
                        }
                    logger.info(
                        "MCP server '%s': discovered %d tools: %s",
                        name,
                        len(result.tools),
                        [t.name for t in result.tools],
                    )
                except Exception as e:
                    logger.error("Failed to list tools from '%s': %s", name, e)
                finally:
                    # Signal that this server is done initializing
                    evt = _ready_events.get(name)
                    if evt:
                        evt.set()

                # Keep the session alive until cancelled
                try:
                    await asyncio.Future()  # block forever
                except asyncio.CancelledError:
                    pass

    except Exception as e:
        logger.error("Failed to start MCP server '%s': %s", name, e)
    finally:
        _sessions.pop(name, None)
        # Signal ready on failure too so init doesn't hang
        evt = _ready_events.get(name)
        if evt and not evt.is_set():
            evt.set()


async def initialize(db_keys: dict[str, str] | None = None) -> None:
    """Initialize all enabled MCP servers and discover their tools."""
    global _initialized
    async with _lock:
        if _initialized:
            return

        config = _load_config()
        servers = config.get("servers", {})

        for name, srv_config in servers.items():
            if not srv_config.get("enabled", True):
                logger.info("MCP server '%s' disabled, skipping", name)
                continue

            # Launch each server as a background task
            evt = asyncio.Event()
            _ready_events[name] = evt
            task = asyncio.create_task(_run_server(name, srv_config, db_keys))
            _tasks[name] = task

        # Wait for all servers to finish init (with timeout)
        if _ready_events:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*(e.wait() for e in _ready_events.values())),
                    timeout=15,
                )
            except asyncio.TimeoutError:
                logger.warning("MCP init timed out — some servers may not be ready")
        _initialized = True


async def shutdown() -> None:
    """Shutdown all MCP sessions and servers."""
    global _initialized
    for name, task in list(_tasks.items()):
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    _tasks.clear()
    _sessions.clear()
    _tools.clear()
    _initialized = False
    logger.info("MCP client shutdown complete")


def get_tool_definitions() -> list[dict]:
    """Return OpenAI-compatible tool definitions for all MCP tools."""
    defs = []
    for tool_name, info in _tools.items():
        schema = info.get("schema", {})
        # Build OpenAI function-call compatible definition
        defs.append({
            "type": "function",
            "function": {
                "name": tool_name,
                "description": info.get("description", ""),
                "parameters": schema if isinstance(schema, dict) else {"type": "object", "properties": {}},
            },
        })
    return defs


def get_tool_names() -> set[str]:
    """Return set of all MCP tool names."""
    return set(_tools.keys())


def is_mcp_tool(name: str) -> bool:
    """Check if a tool name is an MCP tool."""
    return name in _tools


async def call_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Call an MCP tool and return the result as text."""
    if tool_name not in _tools:
        return f"Error: MCP tool '{tool_name}' not found"

    info = _tools[tool_name]
    server_name = info["server"]
    original_name = info["original_name"]

    session = _sessions.get(server_name)
    if not session:
        return f"Error: MCP server '{server_name}' not connected"

    try:
        result = await session.call_tool(original_name, arguments)

        # Extract text content from result
        parts = []
        for content in result.content:
            if hasattr(content, "text"):
                parts.append(content.text)
            elif hasattr(content, "data"):
                parts.append(str(content.data))
            else:
                parts.append(str(content))

        output = "\n".join(parts)
        logger.info("MCP tool '%s' returned %d chars", tool_name, len(output))
        return output

    except Exception as e:
        logger.error("MCP tool '%s' failed: %s", tool_name, e)
        return f"Error calling MCP tool '{tool_name}': {e}"


async def ensure_initialized(db=None) -> None:
    """Initialize MCP if not already done. Pulls API keys from DB if available."""
    if _initialized:
        return

    db_keys = {}
    if db:
        try:
            keys = await db.get_api_keys("default")
            if isinstance(keys, dict):
                # Flatten: both the raw keys and uppercased versions
                for k, v in keys.items():
                    if v:
                        db_keys[k] = v
                        db_keys[k.upper()] = v
        except Exception as e:
            logger.warning("Could not load DB keys for MCP: %s", e)

    await initialize(db_keys)
