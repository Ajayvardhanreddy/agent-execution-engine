"""
Engineering Assistant Agent eval dataset — 10 benchmark cases.

Mock data from demos/engineering_agent/tools.py:
  authenticate_user  — defined in src/auth/service.py:42, used in 2 other files
  rate_limit         — class in src/middleware/rate_limit.py
  sql injection      — raw f-string queries in src/db/queries.py (vulnerable)
  PR-42              — auth endpoint, 1 critical security issue, 1 warning
  PR-99              — docs-only, clean, no issues
  PR-17              — DB refactor, 2 warnings
  backend/pip        — 4 outdated, 2 vulnerable (requests HIGH, cryptography CRITICAL)
  frontend/npm       — 4 outdated, 2 vulnerable (axios MEDIUM, lodash HIGH)
"""
from __future__ import annotations

from engine.evals.base import EvalCase

ENGINEERING_CASES: list[EvalCase] = [

    # ── Code search ────────────────────────────────────────────────────────────

    EvalCase(
        case_id="eng_001",
        description="Find where authenticate_user is defined",
        agent_id="engineering_agent",
        input="Where is the authenticate_user function defined?",
        expected_status="completed",
        expected_tools_called=["code_search"],
        answer_must_contain=["src/auth/service.py"],
        max_cost_usd=0.06,
        tags=["code_search", "definition"],
    ),

    EvalCase(
        case_id="eng_002",
        description="Find all usages of rate_limit across the codebase",
        agent_id="engineering_agent",
        input="Find all places where rate limiting is used or defined in the backend repo.",
        expected_status="completed",
        expected_tools_called=["code_search"],
        answer_must_contain=["rate_limit"],
        max_cost_usd=0.06,
        tags=["code_search", "usage"],
    ),

    EvalCase(
        case_id="eng_003",
        description="Search for SQL injection vulnerabilities",
        agent_id="engineering_agent",
        input="Search the codebase for potential SQL injection vulnerabilities.",
        expected_status="completed",
        expected_tools_called=["code_search"],
        answer_must_contain=["sql", "queries.py"],
        max_cost_usd=0.06,
        tags=["code_search", "security"],
    ),

    # ── File read ──────────────────────────────────────────────────────────────

    EvalCase(
        case_id="eng_004",
        description="Read and explain src/auth/service.py",
        agent_id="engineering_agent",
        input="Show me the contents of src/auth/service.py and tell me what it does.",
        expected_status="completed",
        expected_tools_called=["file_read"],
        answer_must_contain=["authenticate_user"],
        max_cost_usd=0.06,
        tags=["file_read"],
    ),

    EvalCase(
        case_id="eng_005",
        description="Read a file that does not exist — graceful handling",
        agent_id="engineering_agent",
        input="Read the file src/nonexistent/module.py",
        expected_status="completed",
        expected_tools_called=["file_read"],
        unexpected_tools_called=["code_search"],
        answer_must_not_contain=["authenticate_user"],
        max_cost_usd=0.06,
        tags=["file_read", "not_found"],
        notes="Tool returns a not-found message; agent should handle gracefully",
    ),

    # ── PR review ──────────────────────────────────────────────────────────────

    EvalCase(
        case_id="eng_006",
        description="Review PR-42 — must surface the critical security issue",
        agent_id="engineering_agent",
        input="Review PR-42 in the backend repo before I merge it.",
        expected_status="completed",
        expected_tools_called=["pr_review"],
        answer_must_contain=["critical", "timing"],
        answer_must_not_contain=["no issues", "looks good", "approved"],
        max_cost_usd=0.08,
        tags=["pr_review", "security"],
        notes="PR-42 has a critical timing-attack vulnerability — must be called out",
    ),

    EvalCase(
        case_id="eng_007",
        description="Review PR-99 — docs only, should be clean",
        agent_id="engineering_agent",
        input="Is PR-99 safe to merge?",
        expected_status="completed",
        expected_tools_called=["pr_review"],
        answer_must_contain=["PR-99"],
        answer_must_not_contain=["critical", "vulnerability"],
        max_cost_usd=0.06,
        tags=["pr_review", "clean"],
        notes="PR-99 has zero issues — agent should confirm it is clean",
    ),

    EvalCase(
        case_id="eng_008",
        description="Review PR-17 — DB refactor with warnings",
        agent_id="engineering_agent",
        input="Review the database refactor in PR-17. Should we merge it?",
        expected_status="completed",
        expected_tools_called=["pr_review"],
        answer_must_contain=["PR-17", "warning"],
        max_cost_usd=0.08,
        tags=["pr_review", "performance"],
    ),

    # ── Dependency check ───────────────────────────────────────────────────────

    EvalCase(
        case_id="eng_009",
        description="Backend pip dependency audit — must surface critical CVE",
        agent_id="engineering_agent",
        input="Check the backend repo's pip dependencies for vulnerabilities.",
        expected_status="completed",
        expected_tools_called=["dependency_check"],
        answer_must_contain=["cryptography", "critical"],
        max_cost_usd=0.08,
        tags=["dependency_check", "security", "pip"],
        notes="cryptography has a CRITICAL CVE — must be called out explicitly",
    ),

    # ── Multi-step ─────────────────────────────────────────────────────────────

    EvalCase(
        case_id="eng_010",
        description="Multi-step: find SQL injection, then read the vulnerable file",
        agent_id="engineering_agent",
        input="Search for SQL injection patterns in the codebase, then show me the actual vulnerable code.",
        expected_status="completed",
        expected_tools_called=["code_search", "file_read"],
        answer_must_contain=["queries.py"],
        max_cost_usd=0.10,
        tags=["code_search", "file_read", "multi_step", "security"],
        notes="Requires two tool calls: code_search then file_read on queries.py",
    ),
]
