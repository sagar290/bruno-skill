"""Java Spring Boot route scanner."""

from __future__ import annotations

import re

from .common import join_url_paths, normalize_path, RouteInfo


def scan_java_spring_file_for_routes(filepath: str) -> list[RouteInfo]:
    """Scan Java Spring Boot files for @RequestMapping, @GetMapping, etc."""
    routes: list[RouteInfo] = []
    class_prefix = ""

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return routes

    request_mapping_class = re.search(
        r"@RequestMapping\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"']", content
    )
    if request_mapping_class:
        class_prefix = request_mapping_class.group(1)

    method_patterns = [
        (r"@GetMapping\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"']", "GET"),
        (r"@PostMapping\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"']", "POST"),
        (r"@PutMapping\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"']", "PUT"),
        (r"@DeleteMapping\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"']", "DELETE"),
        (r"@PatchMapping\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"']", "PATCH"),
        (
            r"@RequestMapping\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"'][^)]*method\s*=\s*RequestMethod\.(\w+)",
            None,
        ),
    ]

    seen_paths: set[str] = set()
    for pattern, default_method in method_patterns:
        for match in re.finditer(pattern, content):
            path = match.group(1)
            if default_method:
                method = default_method
            elif match.lastindex and match.lastindex >= 2:
                method = match.group(2).upper()
            else:
                method = "GET"
            full_path = join_url_paths(class_prefix, path)
            routes.append({"method": method.upper(), "path": normalize_path(full_path), "source": filepath})
            seen_paths.add(path)

    bare_request_mapping = re.compile(
        r"@RequestMapping\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"'][^)]*\)"
    )
    for match in bare_request_mapping.finditer(content):
        path = match.group(1)
        if path == class_prefix and class_prefix:
            continue
        if path in seen_paths:
            continue
        full_path = join_url_paths(class_prefix, path)
        for method in ["GET", "POST", "PUT", "DELETE"]:
            routes.append({"method": method, "path": normalize_path(full_path), "source": filepath})

    return routes