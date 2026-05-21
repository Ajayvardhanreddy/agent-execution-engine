from __future__ import annotations

import asyncio
import random


class RetryPolicy:
    """Exponential backoff with optional jitter."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        jitter: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def delay_for(self, attempt: int) -> float:
        """Return the sleep duration (seconds) for the given attempt number (0-indexed)."""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        if self.jitter:
            delay *= 0.5 + random.random() * 0.5  # ±50% jitter
        return delay

    async def sleep(self, attempt: int) -> None:
        await asyncio.sleep(self.delay_for(attempt))


# Singletons for common scenarios
LLM_RETRY = RetryPolicy(max_retries=3, base_delay=1.0, max_delay=10.0)
MEMORY_RETRY = RetryPolicy(max_retries=2, base_delay=0.5, max_delay=4.0)
