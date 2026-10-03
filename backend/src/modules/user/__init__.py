"""User module for user management."""

from importlib import import_module

__all__ = [
    # Enums
    "OAuthProvider",
    # Models
    "UserModel",
    # Schemas
    "UserSchema",
    "UserBase",
    "UserCreate",
    "UserDelete",
    "UserRead",
    "UserRestoreDeleted",
    "UserTierUpdate",
    "UserUpdate",
    "UserUpdateInternal",
]

_MODULE_ATTRS = {
    "OAuthProvider": ".enums",
    "UserModel": ".models",
    "UserSchema": ".schemas",
    "UserBase": ".schemas",
    "UserCreate": ".schemas",
    "UserDelete": ".schemas",
    "UserRead": ".schemas",
    "UserRestoreDeleted": ".schemas",
    "UserTierUpdate": ".schemas",
    "UserUpdate": ".schemas",
    "UserUpdateInternal": ".schemas",
}


def __getattr__(name: str):
    module_name = _MODULE_ATTRS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
