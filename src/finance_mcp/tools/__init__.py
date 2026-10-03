from collections.abc import Awaitable, Callable

from mcp.types import TextContent, Tool

ToolHandler = Callable[[dict], Awaitable[list[TextContent]]]
ToolRegistration = tuple[Tool, ToolHandler]
