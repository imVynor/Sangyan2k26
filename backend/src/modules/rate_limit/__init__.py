"""Rate limiting feature.

This module contains the domain models and CRUD operations for rate limits.
The actual implementation of rate limiting is in the infrastructure layer.
"""

from .crud import crud_rate_limits
from importlib import import_module

__all__ = [
    "RateLimitCreate",
    "RateLimitUpdate",
    "RateLimitRead",
    "RateLimit",
    "crud_rate_limits",
]

_MODULE_ATTRS = {
    "RateLimitCreate": ".schemas",
    "RateLimitRead": ".schemas",
    "RateLimitUpdate": ".schemas",
    "RateLimit": ".models",
    "crud_rate_limits": ".crud",
}


def __getattr__(name: str):
    module_name = _MODULE_ATTRS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
