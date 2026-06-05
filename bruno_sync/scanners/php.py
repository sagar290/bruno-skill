"""PHP Laravel route scanner."""

from __future__ import annotations

import re

from .common import join_url_paths, normalize_path, RouteInfo


def scan_laravel_file_for_routes(filepath: str) -> list[RouteInfo]:
    """Scan PHP files for Laravel route definitions.

    Supports:
    - Route::get('/path', ...), Route::post(...), etc.
    - Route::resource('name', Controller::class)
    - Route::apiResource('name', Controller::class)
    - Route::prefix('...')->group(...) with nested routes
    - Route::middleware(...)->prefix('...')->group(...)
    """
    routes: list[RouteInfo] = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return routes

    prefix = ""

    prefix_pattern = re.compile(
        r"Route::prefix\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
    )
    prefix_matches = prefix_pattern.findall(content)
    if len(prefix_matches) == 1:
        prefix = prefix_matches[0]

    method_pattern = re.compile(
        r"Route::(get|post|put|delete|patch|options|head)\s*\(\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )
    for match in method_pattern.finditer(content):
        method = match.group(1).upper()
        path = match.group(2)
        full_path = join_url_paths(prefix, path) if prefix else path
        routes.append({"method": method, "path": normalize_path(full_path), "source": filepath})

    resource_pattern = re.compile(
        r"Route::(apiResource|resource)\s*\(\s*['\"]([^'\"]+)['\"]",
    )
    for match in resource_pattern.finditer(content):
        kind = match.group(1)
        name = match.group(2)
        suffix = "" if kind == "apiResource" else "/create"
        base_path = join_url_paths(prefix, name) if prefix else f"/{name}"
        base = normalize_path(base_path)
        if kind == "apiResource":
            resource_routes = [
                ("GET", base),
                ("POST", base),
                ("GET", normalize_path(f"{base}/{{id}}")),
                ("PUT", normalize_path(f"{base}/{{id}}")),
                ("PATCH", normalize_path(f"{base}/{{id}}")),
                ("DELETE", normalize_path(f"{base}/{{id}}")),
            ]
        else:
            resource_routes = [
                ("GET", base),
                ("GET", normalize_path(f"{base}/create")),
                ("POST", base),
                ("GET", normalize_path(f"{base}/{{id}}")),
                ("GET", normalize_path(f"{base}/{{id}}/edit")),
                ("PUT", normalize_path(f"{base}/{{id}}")),
                ("PATCH", normalize_path(f"{base}/{{id}}")),
                ("DELETE", normalize_path(f"{base}/{{id}}")),
            ]
        for method, path in resource_routes:
            routes.append({"method": method, "path": path, "source": filepath})

    any_pattern = re.compile(
        r"Route::any\s*\(\s*['\"]([^'\"]+)['\"]",
    )
    for match in any_pattern.finditer(content):
        path = match.group(1)
        full_path = join_url_paths(prefix, path) if prefix else path
        for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            routes.append({"method": method, "path": normalize_path(full_path), "source": filepath})

    match_pattern = re.compile(
        r"Route::match\s*\(\s*\[([^\]]+)\]\s*,\s*['\"]([^'\"]+)['\"]",
    )
    for match in match_pattern.finditer(content):
        methods_str = match.group(1)
        path = match.group(2)
        full_path = join_url_paths(prefix, path) if prefix else path
        for m in re.findall(r"['\"]?(\w+)['\"]?", methods_str):
            routes.append({"method": m.upper(), "path": normalize_path(full_path), "source": filepath})

    return routes