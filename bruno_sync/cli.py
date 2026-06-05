#!/usr/bin/env python3
"""Bruno Collection Sync CLI — entry point for ``bruno-sync`` command."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .bru import find_matching_file, scan_collection
from .collection import (
    dedup_collection,
    initialize_collection,
    prune_orphaned_files,
    set_dry_run,
    sync_endpoint_to_bru,
)
from .log import print_error, print_info, print_success, print_warning, set_verbosity
from .parsers import load_config, parse_dotenv, parse_yaml, resolve_collection_dir
from .scanner import scan_directory
from .scanners.common import AUTO_SYNC_FOLDER

VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Bruno Collection Sync Tool — Automate .bru file management across stack codebases."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed debug output"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress all non-error output"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Scan codebase and sync to Bruno Collection")
    sync_parser.add_argument("--config", help="Path to config.yaml configuration file")
    sync_parser.add_argument("--env", help="Path to .env configuration file")
    sync_parser.add_argument("--project-root", default=".", help="Root directory of the project to scan")
    sync_parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files")
    sync_parser.add_argument("--prune", action="store_true", help="Remove orphaned .bru files for deleted routes")
    sync_parser.add_argument("--dedup", action="store_true", help="Remove duplicate .bru files for the same endpoint")

    # add-endpoint
    VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
    add_parser = subparsers.add_parser("add-endpoint", help="Manually append an endpoint to the collection")
    add_parser.add_argument("--method", required=True, help=f"HTTP method ({', '.join(sorted(VALID_METHODS))})")
    add_parser.add_argument("--path", required=True, help="Endpoint request path (e.g. /api/users)")
    add_parser.add_argument("--name", help="Optional name for the request")
    add_parser.add_argument("--config", help="Path to config.yaml configuration file")
    add_parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files")

    # prune
    prune_parser = subparsers.add_parser("prune", help="Remove orphaned .bru files for routes no longer in codebase")
    prune_parser.add_argument("--config", help="Path to config.yaml configuration file")
    prune_parser.add_argument("--env", help="Path to .env configuration file")
    prune_parser.add_argument("--project-root", default=".", help="Root directory of the project to scan")
    prune_parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Verbosity
    if getattr(args, "quiet", False):
        set_verbosity(0)
    elif getattr(args, "verbose", False):
        set_verbosity(2)
    else:
        set_verbosity(1)

    # Dry-run mode
    dry_run = getattr(args, "dry_run", False)
    set_dry_run(dry_run)
    if dry_run:
        print_info("DRY-RUN MODE: No files will be written or deleted")

    project_root = os.path.abspath(getattr(args, "project_root", "."))
    cfg = load_config(project_root)

    # Override config with CLI arguments
    if hasattr(args, "config") and args.config:
        if os.path.exists(args.config):
            with open(args.config, "r", encoding="utf-8") as f:
                ycfg = parse_yaml(f.read())
                bruno_c = ycfg.get("bruno") or ycfg.get("BRUNO") or ycfg
                if isinstance(bruno_c, dict):
                    cfg["collection_path"] = bruno_c.get("collection_path", cfg["collection_path"])
                    cfg["collection_name"] = bruno_c.get("collection_name", cfg["collection_name"])
                    cfg["base_url"] = bruno_c.get("base_url", cfg["base_url"])
        else:
            print_error(f"Config file not found: {args.config}")
            sys.exit(1)

    if hasattr(args, "env") and args.env:
        if os.path.exists(args.env):
            with open(args.env, "r", encoding="utf-8") as f:
                ecfg = parse_dotenv(f.read())
                if "BRUNO_COLLECTION_PATH" in ecfg:
                    cfg["collection_path"] = ecfg["BRUNO_COLLECTION_PATH"]
                if "BRUNO_COLLECTION_NAME" in ecfg:
                    cfg["collection_name"] = ecfg["BRUNO_COLLECTION_NAME"]
        else:
            print_error(f"Env file not found: {args.env}")
            sys.exit(1)

    collection_dir = resolve_collection_dir(project_root, cfg["collection_path"])

    # ---- sync ----
    if args.command == "sync":
        _cmd_sync(args, cfg, collection_dir, project_root)

    # ---- add-endpoint ----
    elif args.command == "add-endpoint":
        _cmd_add_endpoint(args, cfg, collection_dir)

    # ---- prune ----
    elif args.command == "prune":
        _cmd_prune(args, collection_dir, project_root)


def _cmd_sync(args, cfg: dict, collection_dir: str, project_root: str) -> None:
    initialize_collection(collection_dir, cfg["collection_name"])

    print_info(f"Scanning existing Bruno collection at {collection_dir}...")
    exact_index, all_entries = scan_collection(collection_dir)
    print_info(f"Indexed {len(all_entries)} existing HTTP requests in collection.")

    if getattr(args, "dedup", False):
        removed = dedup_collection(collection_dir, all_entries)
        print_info(f"Dedup: removed {removed} duplicate file(s)")
        exact_index, all_entries = scan_collection(collection_dir)

    print_info(f"Scanning project files under {project_root}...")
    routes = scan_directory(project_root)
    print_info(f"Found {len(routes)} unique API endpoints in codebase.")

    if not routes:
        print_warning("No API endpoints were automatically detected. Existing collection was left unchanged.")
        return

    stats: dict[str, int] = {"preserved": 0, "updated": 0, "added": 0, "error": 0}

    for idx, route in enumerate(routes, start=1):
        existing_filepath = find_matching_file(route["method"], route["path"], exact_index, all_entries)
        result = sync_endpoint_to_bru(
            collection_dir=collection_dir,
            method=route["method"],
            path=route["path"],
            base_url=cfg["base_url"],
            seq=idx,
            existing_filepath=existing_filepath,
        )
        stats[result] = stats.get(result, 0) + 1

    if getattr(args, "prune", False):
        pruned = prune_orphaned_files(collection_dir, routes)
        print_info(f"Pruned {pruned} orphaned file(s)")

    print_success(
        f"Sync complete at {collection_dir}: "
        f"{stats.get('preserved', 0)} preserved, "
        f"{stats.get('updated', 0)} updated, "
        f"{stats.get('added', 0)} added to {AUTO_SYNC_FOLDER}/, "
        f"{stats.get('error', 0)} errors"
    )
    print_info("Manual folders and requests were not removed or reorganized.")


def _cmd_add_endpoint(args, cfg: dict, collection_dir: str) -> None:
    method = args.method.upper()
    if method not in VALID_METHODS:
        print_error(f"Invalid HTTP method: {args.method}. Must be one of: {', '.join(sorted(VALID_METHODS))}")
        sys.exit(1)
    path = args.path
    if not path.startswith("/"):
        print_warning(f"Path '{path}' does not start with '/'. Prepending it automatically.")
        path = f"/{path}"

    initialize_collection(collection_dir, cfg["collection_name"])
    exact_index, all_entries = scan_collection(collection_dir)
    existing_filepath = find_matching_file(method, path, exact_index, all_entries)
    result = sync_endpoint_to_bru(
        collection_dir=collection_dir,
        method=method,
        path=path,
        base_url=cfg["base_url"],
        existing_filepath=existing_filepath,
    )
    print_success(f"Endpoint {method} {path} \u2014 {result}")


def _cmd_prune(args, collection_dir: str, project_root: str) -> None:
    initialize_collection(collection_dir, "Pruned Collection")
    print_info(f"Scanning project files under {project_root}...")
    routes = scan_directory(project_root)
    print_info(f"Found {len(routes)} active API endpoints in codebase.")

    print_info(f"Scanning existing Bruno collection at {collection_dir}...")
    prune_orphaned_files(collection_dir, routes)