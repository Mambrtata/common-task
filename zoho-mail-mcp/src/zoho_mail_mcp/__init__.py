"""MCP konektor na Zoho Mail – len na čítanie."""

from .config import READ_ONLY_SCOPES, SCOPE_STRING, Config
from .errors import (
    ConfigError,
    ReadOnlyViolation,
    ZohoApiError,
    ZohoAuthError,
    ZohoMailMCPError,
)

__version__ = "0.1.0"

__all__ = [
    "READ_ONLY_SCOPES",
    "SCOPE_STRING",
    "Config",
    "ConfigError",
    "ReadOnlyViolation",
    "ZohoApiError",
    "ZohoAuthError",
    "ZohoMailMCPError",
    "__version__",
]
