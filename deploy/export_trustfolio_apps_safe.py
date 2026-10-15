#!/usr/bin/env python3
"""Export allowlisted TrustFolio app source from the VPS to a binary tar stream.

Run using: ssh host 'python3 -' < this_file > source.tar.gz
No runtime data, credentials, logs, or deployment configuration are exported.
"""
import os
import sys
import tarfile
from pathlib import Path

SOURCE = Path.home() / "apps" / "trustfolio"
PROJECTS = ("trustfolio-main", "node-backend", "trustfolio_admin")
BLOCKED_DIRS = {
    ".git", ".next", ".venv", "venv", "node_modules", "build", "dist",
    "__pycache__", ".gradle", ".expo", ".dart_tool", ".idea", "vendor",
    "coverage", "logs", "tmp", "cache", "uploads", "backups",
    "backup", "releases", "data", "storage", ".firebase"
}
SOURCE_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".json", ".css",
    ".scss", ".md", ".mdx", ".html", ".svg", ".png", ".jpg",
    ".jpeg", ".webp", ".ico", ".yml", ".yaml", ".txt", ".graphql",
    ".gql", ".sh"
}
BLOCKED_SUFFIXES = (".log", ".bak", ".pem", ".key", ".p12", ".pfx", ".jks",
                    ".keystore", ".sqlite", ".db", ".jsonl")
BLOCKED_FILENAME_PARTS = ("credential", "serviceaccount", "service-account",
                          "secret", "password", "private_key", "private-key")
BLOCKED_EXACT = {"p.json", "resp.json", "firebase-adminsdk.json"}
MAX_FILE_BYTES = 1_600_000
MAX_TOTAL_BYTES = 24_000_000


def allowed(name):
    lower = name.lower()
    if name.startswith(".") or lower in BLOCKED_EXACT:
        return False
    if any(fragment in lower for fragment in BLOCKED_FILENAME_PARTS):
        return False
    if lower.endswith(BLOCKED_SUFFIXES):
        return False
    return Path(name).suffix.lower() in SOURCE_EXTENSIONS


def main():
    if not SOURCE.is_dir():
        raise SystemExit("TrustFolio source path is absent")
    paths = []
    total = 0
    counts = {}
    for project in PROJECTS:
        root = SOURCE / project
        if not root.is_dir() or root.is_symlink():
            raise SystemExit("Expected TrustFolio project missing: " + project)
        project_count = 0
        for parent, directories, filenames in os.walk(root, followlinks=False):
            directories[:] = sorted(
                d for d in directories if not d.startswith(".")
                and d not in BLOCKED_DIRS
                and not (Path(parent) / d).is_symlink()
            )
            for name in sorted(filenames):
                if not allowed(name):
                    continue
                file = Path(parent) / name
                if file.is_symlink() or not file.is_file():
                    continue
                size = file.stat().st_size
                if size > MAX_FILE_BYTES:
                    raise SystemExit("Source file too large for safe import: " +
                                     project + "/" + file.relative_to(root).as_posix())
                total += size
                if total > MAX_TOTAL_BYTES:
                    raise SystemExit("Source import exceeds safety size limit")
                arcname = "apps/" + project + "/" + file.relative_to(root).as_posix()
                paths.append((file, arcname, size))
                project_count += 1
        counts[project] = project_count
        if project_count < 5:
            raise SystemExit("Too few source files for project: " + project)
    print("SAFE_APPS_SOURCE_COUNTS=" + str(counts), file=sys.stderr)
    print("SAFE_APPS_TOTAL_BYTES=" + str(total), file=sys.stderr)
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
        for file, arcname, size in paths:
            info = tarfile.TarInfo(name=arcname)
            info.size = size
            info.mode = 0o644
            info.mtime = 0
            with file.open("rb") as body:
                archive.addfile(info, body)


if __name__ == "__main__":
    main()
