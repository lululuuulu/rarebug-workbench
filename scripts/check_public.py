"""Conservative tracked-source checks; not a substitute for review of added data."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "provider key": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}",
    "GitHub token": r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}",
    "local home path": r"/(?:Users|home)/[A-Za-z0-9_.-]+/",
}


def check(root: Path) -> list[str]:
    problems = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(p in {".git", ".venv", "__pycache__", "runs", "build", "dist"} or p.endswith(".egg-info") for p in relative.parts):
            continue
        if not path.is_file():
            continue
        if path.name == ".env" or path.name.startswith(".env."):
            problems.append(f"Environment file must not be published: {relative}")
        if path.suffix not in {".py", ".json", ".md", ".toml", ".yml", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in PATTERNS.items():
            if re.search(pattern, text):
                problems.append(f"{relative}: possible {label}")
        if relative.parts[0] == "data" and path.suffix == ".json":
            if json.loads(text).get("synthetic") is not True:
                problems.append(f"{relative}: missing synthetic marker")
    return problems


if __name__ == "__main__":
    issues = check(ROOT)
    print("\n".join(issues) if issues else "Public-source checks passed; all fixtures explicitly synthetic.")
    raise SystemExit(bool(issues))
