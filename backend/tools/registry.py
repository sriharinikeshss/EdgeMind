"""
Tool Registry — Phase 0 scaffold (M5).

Provides register_tool(), check_tool_permission(), execute_tool().
Phase 4 fills in the real sandbox routing and permission enforcement.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    risk_level: str = "LOW"          # LOW | MEDIUM | HIGH
    allowed_roles: list[str] = field(default_factory=lambda: ["admin", "operator"])
    sandbox_required: bool = False
    network_required: bool = False
    handler: Callable | None = None  # the actual Python callable


class ToolRegistry:
    """
    Central registry for all tools available to the Executor.

    Phase 0: register/list stubs.
    Phase 4: full permission checks, sandbox routing, tool_calls logging.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a new tool. Raises ValueError if already registered."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def list_tools(self) -> list[str]:
        """Return names of all registered tools."""
        return list(self._tools.keys())

    def get_tool(self, name: str) -> ToolDefinition:
        """Retrieve a tool by name. Raises KeyError if not found."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    def check_tool_permission(self, tool_name: str, user_role: str) -> bool:
        """
        Returns True if user_role is allowed to call tool_name.
        TODO Phase 4: wire to RBAC engine (M6).
        """
        tool = self.get_tool(tool_name)
        return user_role in tool.allowed_roles

    def execute_tool(self, tool_name: str, user_role: str, arguments: dict[str, Any]) -> Any:
        """
        Permission-check then invoke the tool handler.
        TODO Phase 4: add sandbox routing and tool_calls DB logging.
        """
        if not self.check_tool_permission(tool_name, user_role):
            raise PermissionError(
                f"Role '{user_role}' is not allowed to call tool '{tool_name}'."
            )
        tool = self.get_tool(tool_name)
        if tool.handler is None:
            raise NotImplementedError(f"Tool '{tool_name}' has no handler registered yet.")
        return tool.handler(**arguments)

    def validate_tool_arguments(self, tool_name: str, arguments: dict) -> bool:
        """
        TODO Phase 4: validate arguments against the tool's input_schema.
        """
        raise NotImplementedError("Argument validation implemented in Phase 4.")


# Module-level singleton used by the Executor
tool_registry = ToolRegistry()
