#!/usr/bin/env python3
"""Validate a public CoMPhy search index without logging its contents."""
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

ALLOWED_HOSTS = {"comphy-lab.org", "blogs.comphy-lab.org"}
MAX_BYTES = 20 * 1024 * 1024


def is_trusted_url(value):
    if (not isinstance(value, str) or not value.startswith("https://")
            or value != value.strip() or "\\" in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and parsed.netloc in ALLOWED_HOSTS
    except ValueError:
        return False


def validate(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Invalid file or size")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Expected a list")
    for entry in data:
        if (not isinstance(entry, dict) or not is_trusted_url(entry.get("url"))
                or not isinstance(entry.get("title"), str)
                or not isinstance(entry.get("content"), str)):
            raise ValueError("Invalid search-index entry")


if __name__ == "__main__":
    try:
        validate(Path(sys.argv[1]))
    except (IndexError, OSError, RecursionError, ValueError):
        sys.exit("Search index rejected; no contents were logged.")
