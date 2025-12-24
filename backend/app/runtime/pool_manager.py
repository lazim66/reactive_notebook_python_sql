"""Connection pool manager for PostgreSQL."""
from __future__ import annotations

from typing import Optional

import asyncpg


class PoolManager:
    """Manages a single asyncpg connection pool for the application."""

    def __init__(self) -> None:
        self._pool: Optional[asyncpg.Pool] = None

    async def initialize(self, dsn: str) -> None:
        """Initialize the connection pool with the given DSN.

        Args:
            dsn: PostgreSQL connection string

        Raises:
            RuntimeError: If pool is already initialized
        """
        if self._pool is not None:
            raise RuntimeError("Pool is already initialized")

        self._pool = await asyncpg.create_pool(
            dsn,
            min_size=2,
            max_size=10,
            max_queries=50000,
            max_inactive_connection_lifetime=300.0,
            command_timeout=60.0,
        )

    async def close(self) -> None:
        """Close the connection pool gracefully."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def get_pool(self) -> asyncpg.Pool:
        """Get the connection pool.

        Returns:
            The active connection pool

        Raises:
            RuntimeError: If pool is not initialized
        """
        if self._pool is None:
            raise RuntimeError("Pool is not initialized")
        return self._pool

    @property
    def is_initialized(self) -> bool:
        """Check if the pool is initialized."""
        return self._pool is not None
