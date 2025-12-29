"""
MemoryGraph Integration
=======================

Integration with MemoryGraph MCP server for invisible memory layer.
"""

from typing import TYPE_CHECKING, Any

from .config import (
    MemoryGraphConfig,
    clear_config_cache,
    get_memorygraph_config,
    get_memorygraph_timeout,
    is_memorygraph_enabled,
)

# Type hints for lazy-loaded exports (helps static analyzers)
if TYPE_CHECKING:
    from .client import MemoryGraphClient as MemoryGraphClient
    from .context import get_context_for_subtask as get_context_for_subtask
    from .extractor import InsightExtractor as InsightExtractor
    from .formatting import format_context as format_context
    from .relationships import infer_relationships as infer_relationships
    from .storage import save_to_memorygraph as save_to_memorygraph

__all__ = [
    # Config (eagerly loaded)
    "is_memorygraph_enabled",
    "get_memorygraph_config",
    "get_memorygraph_timeout",
    "clear_config_cache",
    "MemoryGraphConfig",
    # Client (lazy loaded)
    "MemoryGraphClient",
    # Context retrieval (lazy loaded)
    "get_context_for_subtask",
    "format_context",
    # Storage (lazy loaded)
    "save_to_memorygraph",
    "InsightExtractor",
    "infer_relationships",
]

# Lazy import mapping: attribute name -> (module, attribute)
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "MemoryGraphClient": (".client", "MemoryGraphClient"),
    "get_context_for_subtask": (".context", "get_context_for_subtask"),
    "format_context": (".formatting", "format_context"),
    "save_to_memorygraph": (".storage", "save_to_memorygraph"),
    "InsightExtractor": (".extractor", "InsightExtractor"),
    "infer_relationships": (".relationships", "infer_relationships"),
}


def __getattr__(name: str) -> Any:
    """Lazy import to avoid requiring memorygraph package for config-only imports."""
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        import importlib

        module = importlib.import_module(module_name, package=__name__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
