from __future__ import annotations

import time

# Per-token pricing in USD (input, output)
_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (0.80 / 1_000_000, 4.00 / 1_000_000),
    "claude-sonnet-4-6":         (3.00 / 1_000_000, 15.00 / 1_000_000),
}
_DEFAULT_PRICING = (1.00 / 1_000_000, 5.00 / 1_000_000)


class BudgetTracker:
    def __init__(
        self,
        max_steps: int = 15,
        max_tokens: int = 10_000,
        max_cost_usd: float = 0.50,
        timeout_seconds: int = 90,
    ) -> None:
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.max_cost_usd = max_cost_usd
        self.timeout_seconds = timeout_seconds

        self.steps_taken: int = 0
        self.tokens_used: int = 0
        self.cost_usd: float = 0.0
        self._started_at: float = time.time()

    def increment_step(self) -> None:
        self.steps_taken += 1

    def add_tokens(self, input_tokens: int, output_tokens: int, model: str) -> None:
        self.tokens_used += input_tokens + output_tokens
        in_price, out_price = _PRICING.get(model, _DEFAULT_PRICING)
        self.cost_usd += input_tokens * in_price + output_tokens * out_price

    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.tokens_used)

    def near_token_limit(self, threshold: float = 0.8) -> bool:
        return self.tokens_used >= self.max_tokens * threshold

    def elapsed_seconds(self) -> float:
        return time.time() - self._started_at

    def elapsed_ms(self) -> int:
        return int(self.elapsed_seconds() * 1000)

    def is_exceeded(self) -> tuple[bool, str]:
        if self.steps_taken >= self.max_steps:
            return True, f"max_steps ({self.max_steps}) reached"
        if self.tokens_used >= self.max_tokens:
            return True, f"max_tokens ({self.max_tokens}) reached"
        if self.cost_usd >= self.max_cost_usd:
            return True, f"max_cost_usd (${self.max_cost_usd:.4f}) reached"
        if self.elapsed_seconds() >= self.timeout_seconds:
            return True, f"timeout ({self.timeout_seconds}s) reached"
        return False, ""
