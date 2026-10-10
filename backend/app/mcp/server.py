"""Model Context Protocol (MCP) server integration.

Exposes Blend's hybrid-search retrieval as MCP tools so that any
MCP-compatible client (Claude Desktop, Cursor, Continue.dev, etc.) can
query the knowledge base directly.

Run standalone:
    python -m app.mcp.server
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.core.database import async_session_factory
from app.services.hybrid_search import hybrid_search

log = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "blend_search",
        "description": (
            "Search the Blend knowledge base using hybrid (dense vector + sparse FTS) retrieval. "
            "Returns the most relevant document chunks for the query."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "description": "Number of results to return.",
                },
            },
            "required": ["query"],
        },
    }
]


async def handle_tool_call(tool_name: str, arguments: dict[str, Any]) -> list[dict]:
    """Dispatch an MCP tool call and return response content."""
    if tool_name == "blend_search":
        query = arguments.get("query", "")
        top_k = int(arguments.get("top_k", 5))

        async with async_session_factory() as session:
            results = await hybrid_search(session, query=query, top_k=top_k)

        content = []
        for r in results:
            content.append(
                {
                    "type": "text",
                    "text": (
                        f"[Document: {r.document_title} | Score: {r.score:.4f}]\n"
                        f"{r.content}"
                    ),
                }
            )
        return content

    return [{"type": "text", "text": f"Unknown tool: {tool_name}"}]


async def stdio_server() -> None:
    """Run JSON-RPC over stdio MCP server loop."""
    import sys

    log.info("Blend MCP server started (stdio transport).")
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_event_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            msg = json.loads(line)
            method = msg.get("method", "")
            msg_id = msg.get("id")

            if method == "tools/list":
                response = {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
            elif method == "tools/call":
                params = msg.get("params", {})
                content = await handle_tool_call(
                    params.get("name", ""),
                    params.get("arguments", {}),
                )
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": content},
                }
            elif method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "blend-mcp", "version": "0.1.0"},
                    },
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as exc:  # noqa: BLE001
            log.error("MCP server error: %s", exc)


if __name__ == "__main__":
    asyncio.run(stdio_server())
