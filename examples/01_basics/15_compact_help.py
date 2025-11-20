"""Compact Help

When a configuration has many fields, the help text can become verbose and
difficult to scan. The ``compact_help`` parameter in :func:`tyro.cli()` enables
a more succinct format that omits field descriptions.

In compact mode, users can still access full descriptions via ``--help-verbose``.

Usage:
    # Compact mode (default with compact_help=True):
    python ./15_compact_help.py --help

    # Verbose mode (access full descriptions):
    python ./15_compact_help.py --help-verbose

    # Actually run it:
    python ./15_compact_help.py --host localhost --port 8080
"""

from dataclasses import dataclass
from typing import Literal

import tyro


@dataclass
class ServerConfig:
    """Configuration for a web server."""

    # Network settings.
    host: str = "0.0.0.0"
    """Hostname to bind the server to."""

    port: int = 8000
    """Port number to listen on."""

    workers: int = 4
    """Number of worker processes."""

    timeout: int = 30
    """Request timeout in seconds."""

    # Security settings.
    ssl_enabled: bool = False
    """Enable SSL/TLS encryption."""

    ssl_cert_path: str = "/etc/ssl/cert.pem"
    """Path to SSL certificate file."""

    ssl_key_path: str = "/etc/ssl/key.pem"
    """Path to SSL private key file."""

    # Application settings.
    max_request_size: int = 10485760
    """Maximum request size in bytes."""

    cors_origins: str = "*"
    """Allowed CORS origins (comma-separated)."""

    log_level: Literal["debug", "info", "warning", "error"] = "info"
    """Logging level for the application."""

    log_file: str = "/var/log/server.log"
    """Path to log file."""

    # Performance settings.
    cache_enabled: bool = True
    """Enable response caching."""

    cache_size: int = 1000
    """Maximum number of cached responses."""

    compression_enabled: bool = True
    """Enable response compression."""

    keepalive_timeout: int = 5
    """Keep-alive connection timeout in seconds."""

    # Database settings.
    db_host: str = "localhost"
    """Database server hostname."""

    db_port: int = 5432
    """Database server port."""

    db_name: str = "appdb"
    """Database name."""


if __name__ == "__main__":
    # Parse with compact_help=True to enable compact mode.
    config = tyro.cli(ServerConfig, compact_help=True)
    print(f"Starting server with config:\n{config}")
