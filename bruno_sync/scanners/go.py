"""Go route scanners: Gin, Chi, gorilla/mux, and stdlib net/http."""

from __future__ import annotations

import re

from .common import join_url_paths, normalize_path, RouteInfo


def scan_go_file_for_routes(filepath: str) -> list[RouteInfo]:
    """Resolve Gin group prefixes so routes include full paths (e.g. /api/v1/auth/login)."""
    routes: list[RouteInfo] = []
    prefix_map: dict[str, str] = {}

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return routes

    group_pattern = re.compile(r"(\w+)\s*:=\s*(\w+)\.Group\(\s*[\"']([^\"']+)[\"']")
    route_pattern = re.compile(
        r"(\w+)\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\(\s*[\"']([^\"']+)[\"']"
    )
    direct_route_pattern = re.compile(
        r"(router|engine|r)\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\(\s*[\"']([^\"']+)[\"']"
    )

    for line in lines:
        group_match = group_pattern.search(line)
        if group_match:
            var_name, parent_var, prefix = group_match.groups()
            parent_prefix = prefix_map.get(parent_var, "")
            prefix_map[var_name] = join_url_paths(parent_prefix, prefix)
            continue

        route_match = route_pattern.search(line)
        if route_match:
            var_name, method, path = route_match.groups()
            full_path = join_url_paths(prefix_map.get(var_name, ""), path)
            routes.append({"method": method.upper(), "path": full_path, "source": filepath})
            continue

        direct_match = direct_route_pattern.search(line)
        if direct_match:
            _, method, path = direct_match.groups()
            routes.append({"method": method.upper(), "path": normalize_path(path), "source": filepath})

    return routes


def scan_chi_file_for_routes(filepath: str) -> list[RouteInfo]:
    """Scan Go files using Chi router patterns: r.Get(\"/path\", handler), r.Route(\"/prefix\", ...)"""
    routes: list[RouteInfo] = []
    prefix_map: dict[str, str] = {}
    current_prefix = ""

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return routes

    chi_method_pattern = re.compile(
        r"(\w+)\.(Get|Post|Put|Delete|Patch|Options|Head)\(\s*[\"']([^\"']+)[\"']",
        re.IGNORECASE,
    )
    chi_route_pattern = re.compile(r"(\w+)\.Route\(\s*[\"']([^\"']+)[\"']")
    chi_mount_pattern = re.compile(r"(\w+)\.Mount\(\s*[\"']([^\"']+)[\"']")

    for line in content.splitlines():
        route_match = chi_route_pattern.search(line)
        if route_match:
            var_name, prefix = route_match.groups()
            prefix_map[var_name] = join_url_paths(current_prefix, prefix)
            continue

        mount_match = chi_mount_pattern.search(line)
        if mount_match:
            var_name, mount_path = mount_match.groups()
            prefix_map[var_name] = join_url_paths(current_prefix, mount_path)
            continue

        method_match = chi_method_pattern.search(line)
        if method_match:
            var_name, method, path = method_match.groups()
            full_path = join_url_paths(prefix_map.get(var_name, current_prefix), path)
            routes.append({"method": method.upper(), "path": full_path, "source": filepath})

    return routes


def scan_mux_file_for_routes(filepath: str) -> list[RouteInfo]:
    """Scan Go files using gorilla/mux patterns: r.HandleFunc(\"/path\", handler).Methods(\"GET\")"""
    routes: list[RouteInfo] = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return routes

    func_pattern = re.compile(r"(\w+)\.HandleFunc\(\s*[\"']([^\"']+)[\"']")
    method_pattern = re.compile(r"\.Methods\(\s*[\"']([^\"']+)[\"']")

    lines = content.splitlines()

    for i, line in enumerate(lines):
        func_match = func_pattern.search(line)
        if func_match:
            var_name = func_match.group(1)
            path = func_match.group(2)
            context = line + " ".join(lines[i + 1 : i + 3])
            method_matches = method_pattern.findall(context)
            methods = [m.upper() for m in method_matches] if method_matches else ["GET"]
            for method in methods:
                routes.append({"method": method, "path": normalize_path(path), "source": filepath})

    prefix_pattern = re.compile(r"(\w+)\.PathPrefix\(\s*[\"']([^\"']+)[\"']")
    for line in lines:
        prefix_match = prefix_pattern.search(line)
        if prefix_match:
            pass  # prefix tracking for sub-routers

    return routes