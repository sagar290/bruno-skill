"""JavaScript/TypeScript route scanners: Express, Fastify, Koa, Next.js."""

from __future__ import annotations

import re

from .common import normalize_path, RouteInfo


def scan_nextjs_file_for_routes(filepath: str) -> list[RouteInfo]:
    """Scan Next.js app router directory structure and API route handlers."""
    routes: list[RouteInfo] = []
    filepath_norm = filepath.replace("\\", "/")
    inferred_path: str | None = None

    if "/api/" in filepath_norm:
        raw_path = filepath_norm
        raw_path = re.sub(r"/route\.\w+$", "", raw_path)
        raw_path = re.sub(r"\.\w+$", "", raw_path)
        raw_path = re.sub(r"\[\[?\w+\]\]?", lambda m: ":param", raw_path)
        api_match = re.search(r"/api(/.*)", raw_path)
        if api_match:
            inferred_path = normalize_path(api_match.group(0))
            routes.append({"method": "GET", "path": inferred_path, "source": filepath})

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return routes

    next_handler_pattern = re.compile(
        r"(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s*\(",
    )
    for match in next_handler_pattern.finditer(content):
        method = match.group(1).upper()
        if not any(r["method"] == method for r in routes):
            path = inferred_path if inferred_path else "/"
            routes.append({"method": method, "path": path, "source": filepath})

    export_handler_pattern = re.compile(
        r"export\s+default\s+(?:async\s+)?function\s+\w+\s*\(\s*(?:req|request)\b",
    )
    if export_handler_pattern.search(content):
        if not routes:
            routes.append({"method": "GET", "path": "/", "source": filepath})

    return routes


def scan_fastify_file_for_routes(filepath: str) -> list[RouteInfo]:
    """Scan Fastify route definitions: app.get('/path', ...) or fastify.route({method: 'GET', url: '/path'})."""
    routes: list[RouteInfo] = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return routes

    method_pattern = re.compile(
        r"(?:app|fastify|server|f)\.(get|post|put|delete|patch|options|head)\(\s*[\"']([^\"']+)[\"']",
        re.IGNORECASE,
    )
    for match in method_pattern.finditer(content):
        method = match.group(1).upper()
        path = match.group(2)
        routes.append({"method": method, "path": normalize_path(path), "source": filepath})

    route_object_pattern = re.compile(
        r"(?:fastify|app|server)\.route\s*\(\s*\{[^}]*method\s*:\s*['\"](\w+)['\"][^}]*url\s*:\s*['\"]([^'\"]+)['\"]",
        re.DOTALL,
    )
    for match in route_object_pattern.finditer(content):
        method = match.group(1).upper()
        path = match.group(2)
        routes.append({"method": method, "path": normalize_path(path), "source": filepath})

    return routes


def scan_koa_file_for_routes(filepath: str) -> list[RouteInfo]:
    """Scan Koa router definitions: router.get('/path', ...) or router.register('/path', ['GET'], ...)."""
    routes: list[RouteInfo] = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return routes

    method_pattern = re.compile(
        r"(?:router|route)\.(get|post|put|delete|patch|options|head|del)\(\s*[\"']([^\"']+)[\"']",
        re.IGNORECASE,
    )
    for match in method_pattern.finditer(content):
        method = match.group(1).upper()
        if method == "DEL":
            method = "DELETE"
        path = match.group(2)
        routes.append({"method": method, "path": normalize_path(path), "source": filepath})

    register_pattern = re.compile(
        r"(?:router|route)\.register\(\s*[\"']([^\"']+)[\"']\s*,\s*\[([^\]]+)\]",
    )
    for match in register_pattern.finditer(content):
        path = match.group(1)
        methods_str = match.group(2)
        for method in re.findall(r"[\"'](\w+)[\"']", methods_str):
            routes.append({"method": method.upper(), "path": normalize_path(path), "source": filepath})

    return routes