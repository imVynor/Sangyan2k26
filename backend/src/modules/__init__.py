"""Module package initialization.

Keep this package lightweight so importing a route module does not eagerly load
all SQLAlchemy models and unrelated infrastructure.
"""

from .role.permission_registry import discover_permissions

# Discover permission enums when the package is imported so permission validation
# works during route declaration without requiring a separate bootstrap step.
discover_permissions()

__all__ = ["discover_permissions"]
