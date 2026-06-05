"""Common utilities for scanners and path handling."""

from __future__ import annotations

import os
import re

RouteInfo = dict[str, str]

AUTO_SYNC_FOLDER = "_sync"
COLLECTION_SKIP_DIRS = {".git", "node_modules", "environments"}
HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]

EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    "bruno",
    "bruno-collection",
    "skills",
    ".gemini",
    "_sync",
}

SOURCE_EXTENSIONS = {".go", ".js", ".ts", ".jsx", ".tsx", ".py", ".rb", ".php", ".java"}


def join_url_paths(*parts: str) -> str:
    """Join URL path segments, normalising slashes."""
    segments: list[str] = []
    for part in parts:
        if not part:
            continue
        segments.extend(p for p in part.strip("/").split("/") if p)
    return "/" + "/".join(segments) if segments else "/"


def normalize_path(path: str) -> str:
    """Normalize a URL path: strip query strings, ensure leading slash, collapse repeated slashes."""
    path = path.split("?")[0].strip()
    if not path.startswith("/"):
        path = "/" + path
    return re.sub(r"/+", "/", path).rstrip("/") or "/"