from importlib import import_module

__all__ = [
    # Models
    "TierModel",
    # Schemas
    "TierSchema",
    "TierBase",
    "TierCreate",
    "TierCreateInternal",
    "TierDelete",
    "TierRead",
    "TierUpdate",
    "TierUpdateInternal",
]

_MODULE_ATTRS = {
    "TierModel": ".models",
    "TierSchema": ".schemas",
    "TierBase": ".schemas",
    "TierCreate": ".schemas",
    "TierCreateInternal": ".schemas",
    "TierDelete": ".schemas",
    "TierRead": ".schemas",
    "TierUpdate": ".schemas",
    "TierUpdateInternal": ".schemas",
}


def __getattr__(name: str):
    module_name = _MODULE_ATTRS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
