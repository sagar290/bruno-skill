"""Collection sync: create, update, prune, and deduplicate .bru files."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict

from .bru import (
    find_matching_file,
    get_folder_and_filename,
    parse_bru_blocks,
    request_file_priority,
    scan_collection,
    serialize_bru_blocks,
)
from .log import print_error, print_info, print_success, print_verbose, print_warning
from .scanners.common import AUTO_SYNC_FOLDER, normalize_path

DRY_RUN = False


def set_dry_run(enabled: bool) -> None:
    global DRY_RUN
    DRY_RUN = enabled


def _dry_run_delete(filepath: str) -> None:
    if DRY_RUN:
        print_info(f"[DRY-RUN] Would delete: {filepath}")
    else:
        os.remove(filepath)
        print_info(f"Deleted orphaned file: {filepath}")


def _dry_run_write(filepath: str, content: str) -> None:
    if DRY_RUN:
        print_info(f"[DRY-RUN] Would write: {filepath}")
        return
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def _dry_run_makedirs(path: str) -> None:
    if DRY_RUN:
        return
    os.makedirs(path, exist_ok=True)


def sync_endpoint_to_bru(
    collection_dir: str,
    method: str,
    path: str,
    base_url: str,
    seq: int = 1,
    existing_filepath: str | None = None,
) -> str:
    """
    Create or update a .bru file. When existing_filepath is set, only merge
    missing path params and preserve names, URLs, headers, body, and tests.
    New endpoints are added under the appropriate folder structure.
    """
    method = method.upper()
    path_params = re.findall(r"[:{]([a-zA-Z0-9_]+)}?", path)

    if existing_filepath:
        filepath = existing_filepath
        rel = os.path.relpath(filepath, collection_dir)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                blocks = parse_bru_blocks(f.read())
        except Exception as e:
            print_warning(f"Could not read existing file {rel}: {e}")
            return "error"

        changed = False
        if path_params and "params:path" not in blocks:
            blocks["params:path"] = "\n".join(f"  {param}: " for param in path_params)
            changed = True

        if changed:
            _dry_run_write(filepath, serialize_bru_blocks(blocks))
            print_info(f"Updated existing request (preserved layout): {rel}")
            return "updated"

        print_info(f"Preserved existing request (no changes): {rel}")
        return "preserved"

    subfolder, filename = get_folder_and_filename(path, method)
    target_dir = (
        os.path.join(collection_dir, AUTO_SYNC_FOLDER, subfolder)
        if subfolder
        else os.path.join(collection_dir, AUTO_SYNC_FOLDER)
    )
    _dry_run_makedirs(target_dir)
    filepath = os.path.join(target_dir, filename)

    if os.path.exists(filepath):
        return sync_endpoint_to_bru(
            collection_dir, method, path, base_url, seq=seq, existing_filepath=filepath
        )

    clean_name = f"{method} {path}"
    meta_block = f"  name: {clean_name}\n  type: http\n  seq: {seq}"
    url = f"{base_url}{path}"
    method_block = f"  url: {url}\n  body: none\n  auth: none"

    blocks: dict[str, str] = {
        "meta": meta_block,
        method.lower(): method_block,
    }

    if path_params:
        blocks["params:path"] = "\n".join(f"  {param}: " for param in path_params)

    _dry_run_write(filepath, serialize_bru_blocks(blocks))

    rel = os.path.relpath(filepath, collection_dir)
    print_info(f"Added new request: {rel}")
    return "added"


def prune_orphaned_files(collection_dir: str, active_routes: list[dict[str, str]]) -> int:
    """
    Remove .bru files whose endpoints are no longer in the scanned codebase.
    Only removes files in _sync/ or at the collection root (auto-generated),
    never manually organized files.
    """
    exact_index, all_entries = scan_collection(collection_dir)

    active_keys: set[tuple[str, str]] = set()
    for route in active_routes:
        norm = normalize_path(route["path"])
        active_keys.add((route["method"], norm))

    pruned = 0
    kept = 0
    for key, filepath in exact_index.items():
        rel = os.path.relpath(filepath, collection_dir).replace("\\", "/")

        is_synced = rel.startswith(f"{AUTO_SYNC_FOLDER}/")
        is_root = "/" not in rel

        if not is_synced and not is_root:
            kept += 1
            continue

        if key not in active_keys:
            _dry_run_delete(filepath)
            pruned += 1
        else:
            kept += 1

    print_info(f"Prune check: {pruned} orphaned file(s) removed, {kept} file(s) kept")
    return pruned


def ensure_gitignore(project_root: str) -> None:
    """Ensure _sync/ is listed in the project's .gitignore.

    If a .gitignore exists and does not yet contain ``_sync``, append it.
    If .gitignore does not exist, create one with ``_sync/``.
    """
    gitignore_path = os.path.join(project_root, ".gitignore")

    if os.path.isfile(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        if any(line.strip().rstrip("/") == "_sync" for line in lines):
            return
        needs_newline = lines and lines[-1] != ""
        with open(gitignore_path, "a", encoding="utf-8") as f:
            if needs_newline:
                f.write("\n")
            f.write("_sync/\n")
        print_info(f"Added '_sync/' to {gitignore_path}")
    else:
        if DRY_RUN:
            print_info(f"[DRY-RUN] Would create {gitignore_path} with '_sync/' entry")
            return
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write("_sync/\n")
        print_info(f"Created {gitignore_path} with '_sync/' entry")


def initialize_collection(collection_dir: str, collection_name: str) -> None:
    """Create a bruno.json file at the collection root if not present."""
    bruno_json_path = os.path.join(collection_dir, "bruno.json")

    if os.path.exists(bruno_json_path):
        print_info(f"Existing Bruno Collection detected at {collection_dir}")
        return

    if DRY_RUN:
        print_info(f"[DRY-RUN] Would initialize Bruno Collection '{collection_name}' at {collection_dir}")
        return

    os.makedirs(collection_dir, exist_ok=True)
    bjson = {
        "version": "1",
        "name": collection_name,
        "type": "collection",
        "ignore": ["node_modules", ".git"],
    }
    with open(bruno_json_path, "w", encoding="utf-8") as f:
        json.dump(bjson, f, indent=2)
    print_success(f"Initialized new Bruno Collection '{collection_name}' at {collection_dir}")


def dedup_collection(collection_dir: str, all_entries: list) -> int:
    """
    Remove lower-priority duplicate .bru files for the same endpoint.
    When multiple files map to the same (method, path), keep only the
    highest-priority one (manually organized > _sync/ > root-level).
    """
    endpoint_files: dict[tuple, list[tuple]] = defaultdict(list)
    for method, path, filepath, priority in all_entries:
        endpoint_files[(method, path)].append((filepath, priority))

    removed = 0
    for key, file_list in endpoint_files.items():
        if len(file_list) <= 1:
            continue
        file_list.sort(key=lambda x: x[1], reverse=True)
        for filepath, priority in file_list[1:]:
            _dry_run_delete(filepath)
            removed += 1

    return removed