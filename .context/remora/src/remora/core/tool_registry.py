"""Tool registry for dynamic tool selection."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from structured_agents.types import ToolCall, ToolResult, ToolSchema


@dataclass
class ToolDefinition:
    """Definition of an available tool."""

    name: str
    description: str
    category: str
    factory: Callable[["WorkspaceContext"], Any]


@dataclass
class WorkspaceContext:
    """Workspace context passed to tool factories."""

    root_path: Path
    externals: dict[str, Any]


class FunctionTool:
    """Wrap a coroutine function in the structured-agents Tool protocol."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        self._schema = ToolSchema(
            name=name,
            description=description,
            parameters=parameters,
        )
        self._handler = handler

    @property
    def schema(self) -> ToolSchema:
        return self._schema

    async def execute(
        self, arguments: dict[str, Any], context: ToolCall | None
    ) -> ToolResult:
        call_id = context.id if context else f"call_{uuid.uuid4().hex[:12]}"
        try:
            result = await self._handler(**arguments)
            output = _format_tool_output(result)
            return ToolResult(call_id=call_id, name=self.schema.name, output=output)
        except Exception as exc:
            return ToolResult(
                call_id=call_id,
                name=self.schema.name,
                output=str(exc),
                is_error=True,
            )


class ToolRegistry:
    """Registry for managing available tools and presets."""

    _TOOLS: dict[str, ToolDefinition] = {}

    PRESETS: dict[str, list[str]] = {
        "file_ops": [
            "read_file",
            "write_file",
            "list_dir",
            "file_exists",
            "search_files",
        ],
        "code_analysis": ["discover_symbols"],
        "all": [],
    }

    @classmethod
    def register(
        cls,
        name: str,
        description: str,
        category: str,
        factory: Callable[[WorkspaceContext], Any],
    ) -> None:
        cls._TOOLS[name] = ToolDefinition(name, description, category, factory)
        if name not in cls.PRESETS["all"]:
            cls.PRESETS["all"].append(name)

    @classmethod
    def get_tools(cls, workspace: WorkspaceContext, presets: list[str]) -> list[Any]:
        names: set[str] = set()
        for preset in presets:
            if preset in cls.PRESETS:
                names.update(cls.PRESETS[preset])

        return [
            cls._TOOLS[name].factory(workspace)
            for name in names
            if name in cls._TOOLS
        ]

    @classmethod
    def list_presets(cls) -> dict[str, list[str]]:
        return {k: v for k, v in cls.PRESETS.items() if v}


def _format_tool_output(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, (bool, int, float)):
        return str(result)
    try:
        return json.dumps(result, ensure_ascii=True, default=str)
    except TypeError:
        return str(result)


def _resolve_under_root(root: Path, path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve()
    resolved.relative_to(root)
    return resolved


# Tool registration

def _register_tools() -> None:
    def make_read_file(ctx: WorkspaceContext) -> FunctionTool:
        async def read_file(path: str) -> str:
            return await ctx.externals["read_file"](path)

        return FunctionTool(
            name="read_file",
            description="Read file contents",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=read_file,
        )

    def make_write_file(ctx: WorkspaceContext) -> FunctionTool:
        async def write_file(path: str, content: str) -> bool:
            await ctx.externals["write_file"](path, content)
            return True

        return FunctionTool(
            name="write_file",
            description="Write content to file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            handler=write_file,
        )

    def make_list_dir(ctx: WorkspaceContext) -> FunctionTool:
        async def list_dir(path: str = ".") -> list[str]:
            return await ctx.externals["list_dir"](path)

        return FunctionTool(
            name="list_dir",
            description="List directory contents",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
            handler=list_dir,
        )

    def make_file_exists(ctx: WorkspaceContext) -> FunctionTool:
        async def file_exists(path: str) -> bool:
            return await ctx.externals["file_exists"](path)

        return FunctionTool(
            name="file_exists",
            description="Check if a file exists",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=file_exists,
        )

    def make_search_files(ctx: WorkspaceContext) -> FunctionTool:
        async def search_files(pattern: str) -> list[str]:
            return await ctx.externals["search_files"](pattern)

        return FunctionTool(
            name="search_files",
            description="Search files by glob pattern",
            parameters={
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
            },
            handler=search_files,
        )

    def make_discover_symbols(ctx: WorkspaceContext) -> FunctionTool:
        from remora.core.discovery import discover

        async def discover_symbols(path: str = ".") -> list[dict[str, Any]]:
            full_path = _resolve_under_root(ctx.root_path, path)
            nodes = discover([full_path])
            return [
                {
                    "name": node.name,
                    "type": node.node_type,
                    "file": node.file_path,
                    "line": node.start_line,
                }
                for node in nodes
            ]

        return FunctionTool(
            name="discover_symbols",
            description="Discover code symbols",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
            handler=discover_symbols,
        )

    ToolRegistry.register("read_file", "Read file contents", "file_ops", make_read_file)
    ToolRegistry.register("write_file", "Write to file", "file_ops", make_write_file)
    ToolRegistry.register("list_dir", "List directory", "file_ops", make_list_dir)
    ToolRegistry.register("file_exists", "Check file exists", "file_ops", make_file_exists)
    ToolRegistry.register("search_files", "Search by pattern", "file_ops", make_search_files)
    ToolRegistry.register(
        "discover_symbols",
        "Find code symbols",
        "code_analysis",
        make_discover_symbols,
    )


_register_tools()

__all__ = ["ToolRegistry", "ToolDefinition", "WorkspaceContext", "FunctionTool"]
