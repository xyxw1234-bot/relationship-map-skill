"""Relationship Map Vault plugin.

The plugin deliberately exposes business operations instead of raw SQL. Its
local vault is durable and independent from Hermes session memory; a hosted
Node Engine adapter can replace this storage boundary without changing the
Skill's user-facing behavior.
"""

from .relationship_map_plugin.tools import TOOL_DEFINITIONS, vault_available


def register(ctx) -> None:
    """Register constrained relationship-asset tools once per Hermes process."""
    for name, schema, handler in TOOL_DEFINITIONS:
        ctx.register_tool(
            name=name,
            toolset="relationship_map",
            schema=schema,
            handler=handler,
            check_fn=vault_available,
            emoji="🗺️",
        )
