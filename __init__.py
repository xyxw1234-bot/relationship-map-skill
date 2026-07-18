"""Relationship Map Vault root plugin entry point."""

from pathlib import Path

from .relationship_map_plugin.relationship_map_plugin.tools import TOOL_DEFINITIONS, vault_available


def register(ctx) -> None:
    ctx.register_skill(
        "relationship-map",
        Path(__file__).parent / "skills" / "relationship-map" / "SKILL.md",
        "自然语言管理联系人、客户资料、互动、承诺、待办与表格客户库。",
    )
    for name, schema, handler in TOOL_DEFINITIONS:
        ctx.register_tool(
            name=name,
            toolset="relationship_map",
            schema=schema,
            handler=handler,
            check_fn=vault_available,
            emoji="🗺️",
        )
