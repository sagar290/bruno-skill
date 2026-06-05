"""Ruby route scanner: Rails routing conventions."""

from __future__ import annotations

import re

from .common import normalize_path, RouteInfo


def scan_ruby_file_for_routes(filepath: str) -> list[RouteInfo]:
    """Scan Ruby on Rails routing files for route definitions."""
    routes: list[RouteInfo] = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return routes

    resource_pattern = re.compile(r"resources\s+:(\w+)(?:\s*,\s*only:\s*\[([^\]]+)\])?")
    for match in resource_pattern.finditer(content):
        name = match.group(1)
        only_clause = match.group(2)
        method_map = {
            "index": ("GET", f"/{name}"),
            "show": ("GET", f"/{name}/:id"),
            "create": ("POST", f"/{name}"),
            "update": ("PUT", f"/{name}/:id"),
            "destroy": ("DELETE", f"/{name}/:id"),
        }
        active_methods = ["index", "show", "create", "update", "destroy"]
        if only_clause:
            active_methods = [m.strip().strip(":\"'") for m in only_clause.split(",")]
        for action in active_methods:
            if action in method_map:
                method, path = method_map[action]
                routes.append({"method": method, "path": normalize_path(path), "source": filepath})

    verb_route_pattern = re.compile(r"(?:get|post|put|patch|delete)\s+['\"]([^'\"]+)['\"]", re.IGNORECASE)
    for match in verb_route_pattern.finditer(content):
        path = match.group(1)
        method_name = content[match.start() : match.start() + 10].strip().split()[0].upper()
        routes.append({"method": method_name, "path": normalize_path(path), "source": filepath})

    return routes