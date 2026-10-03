"""Role module for role-based access control."""

from importlib import import_module

__all__ = [
    # Models
    "Role",
    "RolePermission",
    "UserRole",
    # Permissions
    "RolePermissionName",
    # Registry
    "all_permissions",
    "discover_permissions",
    "is_known_permission",
    "permission_groups",
    "register_permissions",
    # Limits
    "PERMISSION_NAME_MAX_LENGTH",
    "ROLE_NAME_MAX_LENGTH",
]

_MODULE_ATTRS = {
    "Role": ".models",
    "RolePermission": ".models",
    "UserRole": ".models",
    "RolePermissionName": ".permissions",
    "all_permissions": ".permission_registry",
    "discover_permissions": ".permission_registry",
    "is_known_permission": ".permission_registry",
    "permission_groups": ".permission_registry",
    "register_permissions": ".permission_registry",
    "PERMISSION_NAME_MAX_LENGTH": ".constants",
    "ROLE_NAME_MAX_LENGTH": ".constants",
}


def __getattr__(name: str):
    module_name = _MODULE_ATTRS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
