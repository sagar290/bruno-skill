"""Bruno (.bru) file format parser, writer, and collection index."""

from __future__ import annotations

import os
import re
from collections import defaultdict

from .log import print_info, print_verbose, print_warning
from .scanners.common import AUTO_SYNC_FOLDER, COLLECTION_SKIP_DIRS, HTTP_METHODS, normalize_path

BLOCK_ORDER = [
    "meta",
    "get", "post", "put", "delete", "patch", "options", "head",
    "headers",
    "params:query",
    "params:path",
    "body:json",
    "body:text",
    "body:form-urlencoded",
    "body:multipart-form",
    "auth",
    "tests",
    "script:pre-request",
    "script:post-response",
]

BruBlocks = dict[str, str]
CollectionIndex = dict[tuple[str, str], str]
CollectionEntries = list[tuple[str, str, str, int]]


def parse_bru_blocks(content: str) -> BruBlocks:
    """
    Parse a .bru file into structured blocks, tracking brace balancing.
    Returns a dict: {block_name: block_content}
    """
    blocks: BruBlocks = {}
    lines = content.splitlines()
    current_block: str | None = None
    block_lines: list[str] = []
    brace_count = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if current_block is None:
            if stripped.endswith("{") and not line.startswith(" ") and not line.startswith("\t"):
                current_block = stripped.split("{")[0].strip()
                block_lines = []
                brace_count = 1
        else:
            brace_count += line.count("{")
            brace_count -= line.count("}")

            if brace_count == 0:
                blocks[current_block] = "\n".join(block_lines)
                current_block = None
            else:
                block_lines.append(line)
        i += 1

    return blocks


def serialize_bru_blocks(blocks: BruBlocks) -> str:
    """Serialize structured blocks back to .bru markup format."""
    output: list[str] = []
    written: set[str] = set()

    for key in BLOCK_ORDER:
        if key in blocks:
            output.append(f"{key} {{\n{blocks[key]}\n}}")
            written.add(key)

    for key, val in blocks.items():
        if key not in written:
            output.append(f"{key} {{\n{val}\n}}")

    return "\n\n".join(output) + "\n"


def extract_path_from_url(url: str) -> str:
    """Extract the URL path from a Bruno request URL (strips vars and host)."""
    path = re.sub(r"\{\{[^}]+\}\}", "", url).strip()
    if "://" in path:
        path = path.split("://", 1)[1]
        path = "/" + path.split("/", 1)[1] if "/" in path else "/"
    return normalize_path(path)


def extract_endpoint_from_bru(content: str) -> tuple[str, str] | None:
    """Return (method, path) for an HTTP .bru file, or None."""
    blocks = parse_bru_blocks(content)
    meta = blocks.get("meta", "")
    meta_compact = re.sub(r"\s+", "", meta.lower())
    if "type:http" not in meta_compact:
        return None

    for method in [m.lower() for m in HTTP_METHODS]:
        if method not in blocks:
            continue
        match = re.search(r"url:\s*(.+)", blocks[method])
        if match:
            return method.upper(), extract_path_from_url(match.group(1).strip())
    return None


def request_file_priority(filepath: str, collection_dir: str) -> int:
    """Prefer manually organized folders over auto-synced or root-level files."""
    rel = os.path.relpath(filepath, collection_dir).replace("\\", "/")
    score = rel.count("/")

    if rel.startswith(f"{AUTO_SYNC_FOLDER}/"):
        score -= 200
    elif "/" not in rel:
        score -= 100

    return score


def scan_collection(collection_dir: str) -> tuple[CollectionIndex, CollectionEntries]:
    """
    Scan an existing Bruno collection and index requests by method + path.
    Returns (exact_index, all_entries) where all_entries supports suffix matching.
    Deduplicates by preferring higher-priority (manually organized) files.
    """
    exact_index: CollectionIndex = {}
    exact_priority: dict[tuple[str, str], int] = {}
    all_entries: CollectionEntries = []

    if not os.path.isdir(collection_dir):
        return exact_index, all_entries

    for root, dirs, files in os.walk(collection_dir):
        dirs[:] = [d for d in dirs if d not in COLLECTION_SKIP_DIRS]
        for filename in files:
            if not filename.endswith(".bru") or filename == "folder.bru":
                continue

            filepath = os.path.join(root, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    endpoint = extract_endpoint_from_bru(f.read())
                if not endpoint:
                    continue

                method, path = endpoint
                key = (method, path)
                priority = request_file_priority(filepath, collection_dir)
                if key not in exact_index or priority > exact_priority[key]:
                    exact_index[key] = filepath
                    exact_priority[key] = priority
                all_entries.append((method, path, filepath, priority))
            except Exception as e:
                print_warning(f"Could not index {filepath}: {e}")

    return exact_index, all_entries


def find_matching_file(
    method: str, path: str, exact_index: CollectionIndex, all_entries: CollectionEntries
) -> str | None:
    """Find an existing .bru file for a route without reorganizing the collection."""
    norm = normalize_path(path)
    key = (method, norm)
    if key in exact_index:
        return exact_index[key]

    candidates: list[tuple[int, int, str]] = []
    for entry_method, entry_path, filepath, priority in all_entries:
        if entry_method != method:
            continue
        if entry_path == norm or entry_path.endswith(norm) or norm.endswith(entry_path):
            candidates.append((priority, len(entry_path), filepath))

    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def make_safe_filename(path_str: str) -> str:
    """Generate a safe filename for a given URL path."""
    safe = path_str.replace(":", "by-").replace("{", "by-").replace("}", "")
    safe = safe.strip("/").replace("/", "-")
    if not safe:
        safe = "root"
    return safe.lower()


def get_folder_and_filename(path_str: str, method: str) -> tuple[str, str]:
    """
    Determine the subdirectory and file name based on route structure.
    E.g. /api/v1/users -> Subdirectory: api/v1, Filename: users-get.bru
    """
    parts = [p for p in path_str.strip("/").split("/") if p]
    if len(parts) > 1:
        folder = os.path.join(*parts[:-1])
        base_name = parts[-1]
    else:
        folder = ""
        base_name = parts[0] if parts else "root"

    folder = folder.replace(":", "_").replace("{", "_").replace("}", "")
    base_name = base_name.replace(":", "by-").replace("{", "by-").replace("}", "").lower()

    filename = f"{base_name}-{method.lower()}.bru"
    return folder, filename