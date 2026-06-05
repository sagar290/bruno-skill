"""File scanner: walk directories and dispatch to language-specific scanners."""

from __future__ import annotations

import os

from .log import print_warning, print_verbose
from .scanners.common import EXCLUDE_DIRS, SOURCE_EXTENSIONS, normalize_path, RouteInfo
from .scanners.go import scan_chi_file_for_routes, scan_go_file_for_routes, scan_mux_file_for_routes
from .scanners.java import scan_java_spring_file_for_routes
from .scanners.javascript import (
    scan_fastify_file_for_routes,
    scan_koa_file_for_routes,
    scan_nextjs_file_for_routes,
)
from .scanners.php import scan_laravel_file_for_routes
from .scanners.python import scan_python_file_for_routes
from .scanners.ruby import scan_ruby_file_for_routes


def scan_file_for_routes(filepath: str) -> list[RouteInfo]:
    """
    Scan a single source file for API routing patterns across multiple stacks.
    Returns a list of dicts: [{'method': 'GET', 'path': '/api/v1/users'}]
    """
    routes: list[RouteInfo] = []
    _, ext = os.path.splitext(filepath)
    if ext not in SOURCE_EXTENSIONS:
        return routes

    if ext == ".go":
        go_routes = scan_go_file_for_routes(filepath)
        routes.extend(go_routes)
        if not go_routes:
            routes.extend(scan_chi_file_for_routes(filepath))
            routes.extend(scan_mux_file_for_routes(filepath))
        return routes

    if ext == ".java":
        return scan_java_spring_file_for_routes(filepath)

    if ext in (".rb",):
        return scan_ruby_file_for_routes(filepath)

    if ext in (".php",):
        return scan_laravel_file_for_routes(filepath)

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if ext in (".js", ".ts", ".jsx", ".tsx"):
            if "/api/" in filepath.replace("\\", "/") or "route" in filepath.lower():
                routes.extend(scan_nextjs_file_for_routes(filepath))
            routes.extend(scan_fastify_file_for_routes(filepath))
            routes.extend(scan_koa_file_for_routes(filepath))

            seen: set[tuple[str, str]] = set()
            unique: list[RouteInfo] = []
            for r in routes:
                k = (r["method"], r["path"])
                if k not in seen:
                    seen.add(k)
                    unique.append(r)
            routes = unique

        import re

        express_pattern = r'(?:app|router|route)\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']'
        for match in re.finditer(express_pattern, content):
            method = match.group(1).upper()
            path = match.group(2)
            routes.append({"method": method, "path": path, "source": filepath})

        if ext in (".py",):
            routes.extend(scan_python_file_for_routes(filepath))

    except Exception as e:
        print_warning(f"Could not scan file {filepath}: {e}")

    return routes


def scan_directory(search_dir: str) -> list[RouteInfo]:
    """Recursively scan a directory for API route definitions."""
    all_routes: list[RouteInfo] = []

    for root, dirs, files in os.walk(search_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            filepath = os.path.join(root, file)
            file_routes = scan_file_for_routes(filepath)
            all_routes.extend(file_routes)

    seen: set[tuple[str, str]] = set()
    unique_routes: list[RouteInfo] = []
    for r in all_routes:
        key = (r["method"], r["path"])
        if key not in seen:
            seen.add(key)
            unique_routes.append(r)

    return unique_routes