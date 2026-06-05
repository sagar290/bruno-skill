"""Python route scanners: Flask, FastAPI, Django-style decorators."""

from __future__ import annotations

import re

from .common import normalize_path, RouteInfo


def scan_python_file_for_routes(filepath: str) -> list[RouteInfo]:
    """Scan Python files for Flask, FastAPI, and Django route patterns."""
    routes: list[RouteInfo] = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return routes

    py_decorator_pattern = r"@(?:app|router|api)\.(get|post|put|delete|patch|api_view)\(\s*[\"']([^\"']+)[\"']"
    for match in re.finditer(py_decorator_pattern, content):
        method = match.group(1).upper()
        if method == "API_VIEW":
            method = "GET"
        path = match.group(2)
        routes.append({"method": method, "path": path, "source": filepath})

    flask_route_pattern = r"@app\.route\(\s*[\"']([^\"']+)[\"'](?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?"
    for match in re.finditer(flask_route_pattern, content):
        path = match.group(1)
        methods_str = match.group(2)
        methods = ["GET"]
        if methods_str:
            methods = [m.strip(" \"'") for m in methods_str.split(",")]
        for method in methods:
            routes.append({"method": method.upper(), "path": path, "source": filepath})

    return routes