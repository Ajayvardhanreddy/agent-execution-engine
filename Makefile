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
	PYTHONPATH=. uv run python evals/runner.py --suite engineering

eval-all:
	PYTHONPATH=. uv run python evals/runner.py --suite all

# Run a single case: make eval-case CASE=support_005
eval-case:
	PYTHONPATH=. uv run python evals/runner.py --suite support --case $(CASE)

# ── Dev ────────────────────────────────────────────────────────────────────────

serve:
	uv run uvicorn engine.api.app:app --reload

demo:
	PYTHONPATH=. uv run python demos/support_agent/agent.py --scenario eligible_refund

demo-eng:
	PYTHONPATH=. uv run python demos/engineering_agent/agent.py --scenario review_pr

lint:
	uv run ruff check engine/ tests/ evals/ demos/

clean-reports:
	rm -f evals/reports/*.json
