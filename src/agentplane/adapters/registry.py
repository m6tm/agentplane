"""Adapter plugin registry.

Built-in adapters are auto-registered.
External adapters can be registered by dropping a Python module into the
adapters/ directory or calling register_adapter() at runtime.
"""

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Type

from agentplane.adapters.base import Adapter

# Registry: adapter_type -> Adapter class
_ADAPTER_REGISTRY: dict[str, Type[Adapter]] = {}


def register_adapter(adapter_cls: Type[Adapter]) -> Type[Adapter]:
    """Decorator / function to register an adapter class."""
    instance = adapter_cls()
    _ADAPTER_REGISTRY[instance.type] = adapter_cls
    return adapter_cls


def get_adapter(type_name: str) -> Adapter | None:
    """Instantiate an adapter by type name."""
    cls = _ADAPTER_REGISTRY.get(type_name)
    if cls is None:
        return None
    return cls()


def list_adapters() -> list[dict]:
    """List all registered adapter metadata."""
    return [cls().describe() for cls in _ADAPTER_REGISTRY.values()]


def _discover_builtin_adapters() -> None:
    """Auto-discover and register built-in adapters."""
    from agentplane.adapters import builtin

    for _, modname, _ in pkgutil.iter_modules(builtin.__path__):
        if modname.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"agentplane.adapters.builtin.{modname}")
            for _, obj in inspect.getmembers(mod):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Adapter)
                    and obj is not Adapter
                    and not getattr(obj, "_abstract", False)
                ):
                    register_adapter(obj)
        except Exception:
            pass


def discover_external_adapters(path: Path | str) -> None:
    """Discover adapter plugins from an external directory."""
    p = Path(path)
    if not p.exists():
        return
    for file in p.glob("*.py"):
        spec = importlib.util.spec_from_file_location(file.stem, file)  # type: ignore[attr-defined]
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)  # type: ignore[attr-defined]
        spec.loader.exec_module(mod)
        for _, obj in inspect.getmembers(mod):
            if (
                inspect.isclass(obj)
                and issubclass(obj, Adapter)
                and obj is not Adapter
            ):
                register_adapter(obj)


# Auto-discover on import
_discover_builtin_adapters()
