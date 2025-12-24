from __future__ import annotations

import asyncio
from typing import AsyncIterator, Set

from .models import SseEvent


class EventBus:
    """Simple per-notebook event bus backed by asyncio queues."""

    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue[SseEvent]] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: SseEvent) -> None:
        async with self._lock:
            for queue in self._subscribers:
                await queue.put(event)

    async def subscribe(self) -> asyncio.Queue[SseEvent]:
        queue: asyncio.Queue[SseEvent] = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[SseEvent]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def stream(self) -> AsyncIterator[SseEvent]:
        queue = await self.subscribe()
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            await self.unsubscribe(queue)


