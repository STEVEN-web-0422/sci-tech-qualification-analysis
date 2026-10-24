# -*- coding: utf-8 -*-
"""Preflight checks before publishing the repository."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {".xlsx", ".xls", ".sqlite", ".db"}
FORBIDDEN_PREFIXES = ("data/raw/", "data/processed/")
FORBIDDEN_FILES = {"outputs/scored_candidates.csv"}
TEXT_SUFFIXES = {".md", ".csv", ".txt", ".py", ".sql", ".json", ".yml", ".yaml", ".ps1", ".sh"}
CODE_PATTERN = re.compile(r"(?<![A-Z0-9])[0-9A-HJ-NPQRTUWXY]{18}(?![A-Z0-9])")


def tracked_files():
    output = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True, encoding="utf-8")
    return output.splitlines()


def main():
    files = tracked_files()
    errors = []
    total_bytes = 0
    for name in files:
        path = ROOT / name
        if not path.exists():
            continue
        total_bytes += path.stat().st_size
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden raw/data file: {name}")
        if name.startswith(FORBIDDEN_PREFIXES) or name in FORBIDDEN_FILES:
            errors.append(f"forbidden path: {name}")
        if path.stat().st_size > 10 * 1024 * 1024:
            errors.append(f"file larger than 10MB: {name}")
        if path.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                continue
            for match in CODE_PATTERN.findall(text):
                if re.search(r"[A-Z]", match):
                    errors.append(f"possible credit code in {name}: {match}")
    print(f"tracked files: {len(files)}")
    print(f"tracked size: {total_bytes / 1024 / 1024:.2f} MB")
    if errors:
        print("PREFLIGHT FAILED")
        for error in errors:
            print(" -", error)
        sys.exit(1)
    print("PREFLIGHT OK: no raw data files or credit-code-like values found in tracked text files.")


if __name__ == "__main__":
    main()
