"""
Engineering Assistant Agent — mocked tool implementations.

All tools return deterministic mock data so scenarios are reproducible
without any real codebase, GitHub access, or package registry.

Tools:
  code_search       — search for symbols/patterns across a codebase
  file_read         — read a file from a repository
  pr_review         — fetch and analyse a pull request
  dependency_check  — check for outdated or vulnerable dependencies
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from engine.tools.schemas import ToolDefinition


# ── Input / Output schemas ─────────────────────────────────────────────────────

class CodeSearchInput(BaseModel):
    query: str
    repo: str = "backend"
    language: str | None = None
    max_results: int = 5


class CodeMatch(BaseModel):
    file: str
    line: int
    snippet: str
    match_type: str      # "definition" | "usage" | "import"


class CodeSearchOutput(BaseModel):
    matches: list[CodeMatch]
    total_found: int
    query: str
    repo: str


class FileReadInput(BaseModel):
    repo: str
    file_path: str
    start_line: int | None = None
    end_line: int | None = None


class FileReadOutput(BaseModel):
    repo: str
    file_path: str
    content: str
    total_lines: int
    language: str


class PRReviewInput(BaseModel):
    pr_id: str
    repo: str = "backend"


class PRIssue(BaseModel):
    severity: str        # "critical" | "warning" | "info"
    category: str        # "security" | "performance" | "style" | "correctness"
    description: str
    file: str
    line: int | None = None
    suggestion: str | None = None


class PRReviewOutput(BaseModel):
    pr_id: str
    repo: str
    title: str
    author: str
    files_changed: list[str]
    additions: int
    deletions: int
    issues: list[PRIssue]
    summary: str
    approved: bool


class DependencyCheckInput(BaseModel):
    repo: str
    package_manager: str = "pip"     # "pip" | "npm" | "cargo"


class Dependency(BaseModel):
    name: str
    current_version: str
    latest_version: str
    is_outdated: bool
    has_vulnerability: bool
    vulnerability_severity: str | None = None   # "critical" | "high" | "medium" | None
    vulnerability_cve: str | None = None


class DependencyCheckOutput(BaseModel):
    repo: str
    package_manager: str
    total_dependencies: int
    outdated_count: int
    vulnerable_count: int
    dependencies: list[Dependency]


# ── Mock data ──────────────────────────────────────────────────────────────────

_CODE_INDEX: dict[str, list[dict]] = {
    "authenticate_user": [
        {"file": "src/auth/service.py",      "line": 42,  "snippet": "def authenticate_user(username: str, password: str) -> User | None:", "match_type": "definition"},
        {"file": "src/api/routes/auth.py",   "line": 18,  "snippet": "    user = authenticate_user(payload['username'], payload['password'])", "match_type": "usage"},
        {"file": "tests/test_auth.py",       "line": 67,  "snippet": "    result = authenticate_user('alice', 'secret')", "match_type": "usage"},
    ],
    "rate_limit": [
        {"file": "src/middleware/rate_limit.py", "line": 10, "snippet": "class RateLimiter:", "match_type": "definition"},
        {"file": "src/middleware/rate_limit.py", "line": 34, "snippet": "    def check_rate_limit(self, key: str, limit: int, window: int) -> bool:", "match_type": "definition"},
        {"file": "src/api/app.py",               "line": 23, "snippet": "from src.middleware.rate_limit import RateLimiter", "match_type": "import"},
    ],
    "database": [
        {"file": "src/db/connection.py",   "line": 8,  "snippet": "class DatabasePool:", "match_type": "definition"},
        {"file": "src/db/connection.py",   "line": 29, "snippet": "    def get_connection(self) -> Connection:", "match_type": "definition"},
        {"file": "src/models/user.py",     "line": 5,  "snippet": "from src.db.connection import DatabasePool", "match_type": "import"},
        {"file": "src/models/order.py",    "line": 5,  "snippet": "from src.db.connection import DatabasePool", "match_type": "import"},
    ],
    "sql injection": [
        {"file": "src/db/queries.py",  "line": 87, "snippet": '    query = f"SELECT * FROM users WHERE id = {user_id}"', "match_type": "usage"},
        {"file": "src/db/queries.py",  "line": 102,"snippet": '    query = f"DELETE FROM sessions WHERE token = {token}"', "match_type": "usage"},
    ],
    "TODO": [
        {"file": "src/auth/service.py",  "line": 91, "snippet": "    # TODO: add MFA support", "match_type": "usage"},
        {"file": "src/api/routes/orders.py", "line": 44, "snippet": "    # TODO: validate address before processing", "match_type": "usage"},
        {"file": "src/db/connection.py", "line": 55, "snippet": "    # TODO: implement connection pooling", "match_type": "usage"},
    ],
}

_FILES: dict[str, dict] = {
    "src/auth/service.py": {
        "content": """\
from __future__ import annotations
import hashlib
from src.db.connection import DatabasePool
from src.models.user import User

db = DatabasePool()

def authenticate_user(username: str, password: str) -> User | None:
    \"\"\"Authenticate a user by username and password.\"\"\"
    conn = db.get_connection()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (username, password_hash)
    ).fetchone()
    if row is None:
        return None
    return User(**row)

def create_session(user_id: int) -> str:
    \"\"\"Create a new session token for the given user.\"\"\"
    import secrets
    token = secrets.token_hex(32)
    conn = db.get_connection()
    conn.execute("INSERT INTO sessions (user_id, token) VALUES (?, ?)", (user_id, token))
    return token

# TODO: add MFA support
""",
        "total_lines": 29,
        "language": "python",
    },
    "src/middleware/rate_limit.py": {
        "content": """\
from __future__ import annotations
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self) -> None:
        self._counters: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        self._counters[key] = [t for t in self._counters[key] if now - t < window]
        if len(self._counters[key]) >= limit:
            return False
        self._counters[key].append(now)
        return True
""",
        "total_lines": 15,
        "language": "python",
    },
    "src/db/queries.py": {
        "content": """\
# WARNING: This file contains unsafe SQL — flagged for refactoring

def get_user_by_id(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)

def delete_session(token):
    query = f"DELETE FROM sessions WHERE token = {token}"
    return db.execute(query)
""",
        "total_lines": 9,
        "language": "python",
    },
}

_PRS: dict[str, dict] = {
    "PR-42": {
        "title": "Add user authentication endpoint",
        "author": "dev-alice",
        "files_changed": ["src/api/routes/auth.py", "src/auth/service.py", "tests/test_auth.py"],
        "additions": 145,
        "deletions": 12,
        "issues": [
            {"severity": "critical", "category": "security",
             "description": "Password comparison uses == instead of hmac.compare_digest — vulnerable to timing attacks.",
             "file": "src/auth/service.py", "line": 15,
             "suggestion": "Use hmac.compare_digest(a, b) instead of a == b for password/token comparison."},
            {"severity": "warning", "category": "correctness",
             "description": "No rate limiting on the /login endpoint — brute-force attacks possible.",
             "file": "src/api/routes/auth.py", "line": 28,
             "suggestion": "Apply the existing RateLimiter middleware to the login route."},
            {"severity": "info", "category": "style",
             "description": "Missing type annotations on internal helper functions.",
             "file": "src/auth/service.py", "line": 38, "suggestion": None},
        ],
        "summary": "Adds login/logout endpoints and session management. Has a critical security issue with timing-safe comparison and a missing rate limit.",
        "approved": False,
    },
    "PR-99": {
        "title": "Update README and add contributing guide",
        "author": "dev-bob",
        "files_changed": ["README.md", "CONTRIBUTING.md"],
        "additions": 210,
        "deletions": 45,
        "issues": [],
        "summary": "Documentation-only PR. No code changes. Clean.",
        "approved": True,
    },
    "PR-17": {
        "title": "Refactor database connection pooling",
        "author": "dev-carol",
        "files_changed": ["src/db/connection.py", "src/db/queries.py", "tests/test_db.py"],
        "additions": 320,
        "deletions": 180,
        "issues": [
            {"severity": "warning", "category": "performance",
             "description": "Connection pool size is hardcoded to 5 — should be configurable via environment variable.",
             "file": "src/db/connection.py", "line": 12,
             "suggestion": "Use os.environ.get('DB_POOL_SIZE', '5') to make it configurable."},
            {"severity": "warning", "category": "correctness",
             "description": "Pool does not handle connection timeouts — queries may hang indefinitely.",
             "file": "src/db/connection.py", "line": 34,
             "suggestion": "Add connect_timeout parameter to connection creation."},
        ],
        "summary": "Moves from single connection to pooling. Two warnings around configurability and timeout handling but no critical issues.",
        "approved": False,
    },
}

_DEPENDENCIES: dict[str, list[dict]] = {
    "backend-pip": [
        {"name": "fastapi",   "current": "0.95.0",  "latest": "0.115.0", "outdated": True,  "vuln": False, "sev": None,       "cve": None},
        {"name": "pydantic",  "current": "1.10.0",  "latest": "2.13.0",  "outdated": True,  "vuln": False, "sev": None,       "cve": None},
        {"name": "requests",  "current": "2.28.0",  "latest": "2.32.3",  "outdated": True,  "vuln": True,  "sev": "high",     "cve": "CVE-2023-32681"},
        {"name": "cryptography","current":"38.0.0", "latest": "44.0.0",  "outdated": True,  "vuln": True,  "sev": "critical", "cve": "CVE-2023-49083"},
        {"name": "uvicorn",   "current": "0.23.0",  "latest": "0.34.0",  "outdated": True,  "vuln": False, "sev": None,       "cve": None},
        {"name": "httpx",     "current": "0.28.1",  "latest": "0.28.1",  "outdated": False, "vuln": False, "sev": None,       "cve": None},
        {"name": "pytest",    "current": "7.4.0",   "latest": "8.3.0",   "outdated": True,  "vuln": False, "sev": None,       "cve": None},
    ],
    "frontend-npm": [
        {"name": "react",      "current": "18.2.0", "latest": "18.3.1",  "outdated": True,  "vuln": False, "sev": None,       "cve": None},
        {"name": "axios",      "current": "0.27.0", "latest": "1.7.9",   "outdated": True,  "vuln": True,  "sev": "medium",   "cve": "CVE-2023-45857"},
        {"name": "lodash",     "current": "4.17.20","latest": "4.17.21", "outdated": True,  "vuln": True,  "sev": "high",     "cve": "CVE-2021-23337"},
        {"name": "typescript", "current": "5.3.0",  "latest": "5.7.3",   "outdated": True,  "vuln": False, "sev": None,       "cve": None},
        {"name": "vite",       "current": "5.4.0",  "latest": "6.1.0",   "outdated": True,  "vuln": False, "sev": None,       "cve": None},
    ],
}


# ── Tool functions ─────────────────────────────────────────────────────────────

async def _code_search(inp: CodeSearchInput) -> dict:
    query_lower = inp.query.lower()
    matches: list[dict] = []
    for keyword, entries in _CODE_INDEX.items():
        if keyword.lower() in query_lower or query_lower in keyword.lower():
            matches.extend(entries)
    matches = matches[:inp.max_results]
    return {
        "matches": matches,
        "total_found": len(matches),
        "query": inp.query,
        "repo": inp.repo,
    }


async def _file_read(inp: FileReadInput) -> dict:
    data = _FILES.get(inp.file_path)
    if data is None:
        # Return a clear not-found message rather than raising
        return {
            "repo": inp.repo,
            "file_path": inp.file_path,
            "content": f"File '{inp.file_path}' not found in repo '{inp.repo}'.",
            "total_lines": 0,
            "language": "unknown",
        }
    content = data["content"]
    if inp.start_line or inp.end_line:
        lines = content.splitlines()
        start = (inp.start_line or 1) - 1
        end = inp.end_line or len(lines)
        content = "\n".join(lines[start:end])
    return {
        "repo": inp.repo,
        "file_path": inp.file_path,
        "content": content,
        "total_lines": data["total_lines"],
        "language": data["language"],
    }


async def _pr_review(inp: PRReviewInput) -> dict:
    pr = _PRS.get(inp.pr_id.upper())
    if pr is None:
        return {
            "pr_id": inp.pr_id, "repo": inp.repo,
            "title": "PR not found", "author": "unknown",
            "files_changed": [], "additions": 0, "deletions": 0,
            "issues": [],
            "summary": f"PR '{inp.pr_id}' not found in repo '{inp.repo}'.",
            "approved": False,
        }
    return {
        "pr_id": inp.pr_id, "repo": inp.repo,
        "title": pr["title"], "author": pr["author"],
        "files_changed": pr["files_changed"],
        "additions": pr["additions"], "deletions": pr["deletions"],
        "issues": pr["issues"],
        "summary": pr["summary"],
        "approved": pr["approved"],
    }


async def _dependency_check(inp: DependencyCheckInput) -> dict:
    key = f"{inp.repo}-{inp.package_manager}"
    deps_raw = _DEPENDENCIES.get(key, [])
    deps = [
        {
            "name": d["name"],
            "current_version": d["current"],
            "latest_version": d["latest"],
            "is_outdated": d["outdated"],
            "has_vulnerability": d["vuln"],
            "vulnerability_severity": d["sev"],
            "vulnerability_cve": d["cve"],
        }
        for d in deps_raw
    ]
    return {
        "repo": inp.repo,
        "package_manager": inp.package_manager,
        "total_dependencies": len(deps),
        "outdated_count": sum(1 for d in deps if d["is_outdated"]),
        "vulnerable_count": sum(1 for d in deps if d["has_vulnerability"]),
        "dependencies": deps,
    }


# ── Tool definitions ───────────────────────────────────────────────────────────

CODE_SEARCH = ToolDefinition(
    name="code_search",
    description=(
        "Search for functions, classes, variables, or patterns across a codebase. "
        "Use this when the user asks where something is defined, wants to find all "
        "usages of a symbol, or needs to locate specific code patterns like SQL queries "
        "or TODO comments. Returns file paths, line numbers, and code snippets. "
        "Specify 'repo' if the user mentions a particular repository."
    ),
    fn=_code_search,
    input_schema=CodeSearchInput,
    output_schema=CodeSearchOutput,
    timeout_seconds=10,
    max_retries=1,
    permission_level="read",
    on_error="return_structured_error",
)

FILE_READ = ToolDefinition(
    name="file_read",
    description=(
        "Read the contents of a specific file from a repository. "
        "Use this when the user asks to see a file, wants to review specific code, "
        "or after a code_search to inspect a match in more detail. "
        "Optionally accepts start_line and end_line to read only a section of the file."
    ),
    fn=_file_read,
    input_schema=FileReadInput,
    output_schema=FileReadOutput,
    timeout_seconds=10,
    max_retries=1,
    permission_level="read",
    on_error="return_structured_error",
)

PR_REVIEW = ToolDefinition(
    name="pr_review",
    description=(
        "Fetch and analyse a pull request for issues. Returns the PR title, author, "
        "files changed, and a list of issues categorised by severity (critical, warning, info) "
        "and type (security, performance, style, correctness). "
        "Use this when the user asks to review a PR, check a pull request for problems, "
        "or wants a summary of what a PR does. Requires a pr_id (e.g. 'PR-42')."
    ),
    fn=_pr_review,
    input_schema=PRReviewInput,
    output_schema=PRReviewOutput,
    timeout_seconds=15,
    max_retries=1,
    permission_level="read",
    on_error="return_structured_error",
)

DEPENDENCY_CHECK = ToolDefinition(
    name="dependency_check",
    description=(
        "Check a repository's dependencies for outdated versions and known security "
        "vulnerabilities. Returns each dependency with its current version, latest version, "
        "and any CVEs. Use this when the user asks about dependency health, security "
        "vulnerabilities in packages, or whether dependencies need updating. "
        "Specify package_manager as 'pip', 'npm', or 'cargo'."
    ),
    fn=_dependency_check,
    input_schema=DependencyCheckInput,
    output_schema=DependencyCheckOutput,
    timeout_seconds=15,
    max_retries=2,
    permission_level="read",
    on_error="return_structured_error",
)

ALL_TOOLS = [CODE_SEARCH, FILE_READ, PR_REVIEW, DEPENDENCY_CHECK]
TOOL_NAMES = [t.name for t in ALL_TOOLS]
