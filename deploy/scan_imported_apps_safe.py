#!/usr/bin/env python3
"""Fail-closed audit before GitHub receives files copied from VPS app source."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps"
PROJECTS = ("trustfolio-main", "node-backend", "trustfolio_admin")
TEXT_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".json",
    ".css", ".scss", ".md", ".mdx", ".html", ".svg",
    ".txt", ".yml", ".yaml", ".graphql", ".gql", ".sh",
}
NON_SOURCE_SEGMENTS = {
    ".git", ".next", ".venv", "venv", "node_modules", "build", "dist",
    "__pycache__", ".gradle", ".expo", ".dart_tool", "vendor",
    "coverage", "logs", "tmp", "cache", "uploads", "backups",
    "backup", "releases", "data", "storage",
}
BLOCKED_NAMES = re.compile(
    r"(?:^|[.\\/_-])(?:env|secret|credential|service.?account|private.?key)(?:$|[.\\/_-])",
    re.IGNORECASE,
)
SECRET_PATTERNS = (
    ("private key", re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub credential", re.compile(rb"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}")),
    ("cloud access key", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
    ("OpenAI credential", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{25,}\b")),
    ("payment credential", re.compile(rb"\b(?:sk_live_|rk_live_)[A-Za-z0-9]{16,}\b")),
    ("embedded MongoDB credentials", re.compile(rb"mongodb(?:\+srv)?://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE)),
)
MAX_BYTES = 24_000_000


def main():
    problems = []
    totals = {}
    total_bytes = 0
    for project in PROJECTS:
        folder = ROOT / project
        if not folder.is_dir() or folder.is_symlink():
            problems.append("project missing: " + project)
            continue
        if not (folder / "package.json").is_file():
            problems.append("package.json missing in " + project)
        else:
            try:
                pkg = json.loads((folder / "package.json").read_text("utf-8"))
                if not isinstance(pkg.get("scripts", {}), dict):
                    problems.append("invalid scripts object in " + project)
            except (ValueError, UnicodeError) as err:
                problems.append("invalid package manifest: " + project + ": " + type(err).__name__)
        count = 0
        for file in folder.rglob("*"):
            if file.is_symlink():
                problems.append("symlink forbidden: " + str(file.relative_to(ROOT)))
                continue
            if not file.is_file():
                continue
            relative = file.relative_to(ROOT)
            if any(part.startswith(".") or part.lower() in NON_SOURCE_SEGMENTS
                   for part in relative.parts):
                problems.append("blocked path included: " + str(relative))
                continue
            if BLOCKED_NAMES.search(relative.as_posix()):
                problems.append("sensitive file name included: " + str(relative))
                continue
            total_bytes += file.stat().st_size
            if file.stat().st_size > 1_600_000:
                problems.append("oversize single source: " + str(relative))
            count += 1
            if file.suffix.lower() in TEXT_EXTENSIONS:
                data = file.read_bytes()
                for tag, expr in SECRET_PATTERNS:
                    if expr.search(data):
                        problems.append("potential " + tag + ": " + str(relative))
                        # Do not print secret values to log, even on failure.
        totals[project] = count
        if count < 5:
            problems.append("incomplete project: " + project)
    if total_bytes > MAX_BYTES:
        problems.append("total source bytes exceed limit")
    print("SAFE_IMPORT_COUNTS:", json.dumps(totals))
    print("SAFE_IMPORT_BYTES:", total_bytes)
    if problems:
        for problem in problems[:35]:
            print("IMPORT_BLOCKED:", problem)
        raise SystemExit("Import rejected: source audit did not pass")
    print("SOURCE_AUDIT_PASSED")


if __name__ == "__main__":
    main()
