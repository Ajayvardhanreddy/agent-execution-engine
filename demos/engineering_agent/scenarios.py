"""
Engineering Assistant Agent — demo scenarios.

Each scenario exercises a different aspect of the engineering agent:
code search, file inspection, PR review, dependency analysis, and
multi-step investigations.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Scenario:
    name: str
    description: str
    user_id: str
    session_id: str
    input: str
    expected_status: str
    notes: str = ""


SCENARIOS: list[Scenario] = [

    Scenario(
        name="find_function",
        description="Locate where authenticate_user is defined across the codebase",
        user_id="eng-alice",
        session_id="eng-sess-001",
        input="Where is the authenticate_user function defined? Which files use it?",
        expected_status="completed",
        notes="Should call code_search and summarise definition + usages",
    ),

    Scenario(
        name="review_pr",
        description="Review PR-42 for security issues before merging",
        user_id="eng-bob",
        session_id="eng-sess-002",
        input="Review PR-42 in the backend repo. I'm about to merge it — are there any issues I should know about?",
        expected_status="completed",
        notes="Should call pr_review, highlight the critical timing-attack issue",
    ),

    Scenario(
        name="dependency_audit",
        description="Full dependency security audit of the backend",
        user_id="eng-carol",
        session_id="eng-sess-003",
        input="Run a dependency check on the backend repo using pip. I need to know if we have any vulnerable packages before our security review next week.",
        expected_status="completed",
        notes="Should call dependency_check, surface cryptography CVE as critical",
    ),

    Scenario(
        name="inspect_file",
        description="Read and explain a specific source file",
        user_id="eng-alice",
        session_id="eng-sess-004",
        input="Show me the contents of src/auth/service.py and explain what it does.",
        expected_status="completed",
        notes="Should call file_read and provide a clear explanation",
    ),

    Scenario(
        name="security_investigation",
        description="Multi-step: find SQL injection patterns, then read the offending file",
        user_id="eng-dave",
        session_id="eng-sess-005",
        input="Search the codebase for SQL injection vulnerabilities. If you find any, show me the actual code.",
        expected_status="completed",
        notes="Should call code_search for 'sql injection', then file_read on queries.py",
    ),
]

SCENARIOS_BY_NAME = {s.name: s for s in SCENARIOS}
