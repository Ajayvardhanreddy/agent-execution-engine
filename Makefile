.PHONY: test eval eval-support eval-engineering eval-case clean-reports lint

# ── Tests ──────────────────────────────────────────────────────────────────────

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

# ── Evals ──────────────────────────────────────────────────────────────────────
# Evals make real Anthropic API calls — they cost money and take time.
# Run locally; do not run in CI.

eval: eval-support

eval-support:
	PYTHONPATH=. uv run python evals/runner.py --suite support

eval-engineering:
	@echo "Engineering agent evals available in Phase 5."
	@echo "Run after Phase 5 is complete: make eval-engineering"

# Run a single case: make eval-case CASE=support_005
eval-case:
	PYTHONPATH=. uv run python evals/runner.py --suite support --case $(CASE)

# ── Dev ────────────────────────────────────────────────────────────────────────

serve:
	uv run uvicorn engine.api.app:app --reload

demo:
	PYTHONPATH=. uv run python demos/support_agent/agent.py --scenario eligible_refund

lint:
	uv run ruff check engine/ tests/ evals/ demos/

clean-reports:
	rm -f evals/reports/*.json
