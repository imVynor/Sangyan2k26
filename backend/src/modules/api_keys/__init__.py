"""API Key Management Module.

This module provides comprehensive API key management functionality
for developer-facing products and API-first business models.

Key Features:
- Secure API key generation and storage
- Permission-based access control
- Usage tracking per API key
- Key rotation and revocation
- Analytics and usage reporting
- Granular permissions system
"""

from importlib import import_module

__all__ = [
    # Models
    "APIKey",
    "KeyUsage",
    "KeyPermission",
    # Schemas
    "APIKeyBase",
    "APIKeyCreate",
    "APIKeyRead",
    "APIKeyResponse",
    "APIKeyUpdate",
    "KeyUsageBase",
    "KeyUsageCreate",
    "KeyUsageRead",
    "KeyPermissionBase",
    "KeyPermissionCreate",
    "KeyPermissionRead",
    "KeyPermissionUpdate",
    "APIKeyWithPermissions",
    "KeyUsageAnalytics",
    "UserAPIKeySummary",
    "APIKeyValidationRequest",
    "APIKeyValidationResponse",
    # CRUD
    "crud_api_keys",
    "crud_key_usage",
    "crud_key_permissions",
    # Service
    "APIKeyService",
    # Enums
    "HTTPMethod",
    "KeyPermissionAction",
    "KeyPermissionResource",
    "KeyStatus",
    "KeyType",
]

_MODULE_ATTRS = {
    "APIKey": ".models",
    "KeyUsage": ".models",
    "KeyPermission": ".models",
    "APIKeyBase": ".schemas",
    "APIKeyCreate": ".schemas",
    "APIKeyRead": ".schemas",
    "APIKeyResponse": ".schemas",
    "APIKeyUpdate": ".schemas",
    "KeyUsageBase": ".schemas",
    "KeyUsageCreate": ".schemas",
    "KeyUsageRead": ".schemas",
    "KeyPermissionBase": ".schemas",
    "KeyPermissionCreate": ".schemas",
    "KeyPermissionRead": ".schemas",
    "KeyPermissionUpdate": ".schemas",
    "APIKeyWithPermissions": ".schemas",
    "KeyUsageAnalytics": ".schemas",
    "UserAPIKeySummary": ".schemas",
    "APIKeyValidationRequest": ".schemas",
    "APIKeyValidationResponse": ".schemas",
    "crud_api_keys": ".crud",
    "crud_key_usage": ".crud",
    "crud_key_permissions": ".crud",
    "APIKeyService": ".service",
    "HTTPMethod": ".enums",
    "KeyPermissionAction": ".enums",
    "KeyPermissionResource": ".enums",
    "KeyStatus": ".enums",
    "KeyType": ".enums",
}


def __getattr__(name: str):
    module_name = _MODULE_ATTRS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
