"""Configuration parsers: YAML, dotenv, bruno.json, and config loading."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from .log import print_info, print_warning

ConfigDict = dict[str, str]

DEFAULT_CONFIG: ConfigDict = {
    "collection_path": "./bruno",
    "collection_name": "Project API",
    "base_url": "{{baseUrl}}",
}


def parse_dotenv(content: str) -> ConfigDict:
    """Parse environment variables from .env content."""
    config: ConfigDict = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            else:
                val = val.split("#")[0].strip()
            config[key] = val
    return config


def _yaml_coerce(val: str) -> Any:
    """Coerce a YAML scalar string to its Python type."""
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    if val.lower() in ("null", "~"):
        return None
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def parse_yaml(content: str) -> dict[str, Any]:
    """
    Light YAML parser handling nested key-values, lists, multi-line strings,
    anchors/aliases, and basic type coercion without external dependencies.
    """
    result: dict[str, Any] = {}
    lines = content.splitlines()
    stack: list[tuple[int, dict, str | None]] = [(0, result, None)]
    anchors: dict[str, Any] = {}
    pending_list_key: str | None = None

    i = 0
    while i < len(lines):
        line = lines[i]
        line_clean = (
            line.split("#")[0] if "#" in line and not ("\"" in line or "'" in line) else line
        )
        stripped = line_clean.strip()

        if not stripped:
            i += 1
            continue

        indent = len(line_clean) - len(line_clean.lstrip(" "))

        if stripped.startswith("- "):
            while len(stack) > 1 and indent <= stack[-1][0]:
                stack.pop()
            parent_indent, parent_dict, list_key = stack[-1]

            if list_key is not None and isinstance(parent_dict.get(list_key), list):
                item_value = stripped[2:].strip().strip("'\"")
                parent_dict[list_key].append(_yaml_coerce(item_value))
            elif pending_list_key is not None:
                stack[-1] = (parent_indent, parent_dict, pending_list_key)
                if pending_list_key not in parent_dict:
                    parent_dict[pending_list_key] = []
                item_value = stripped[2:].strip().strip("'\"")
                parent_dict[pending_list_key].append(_yaml_coerce(item_value))
                pending_list_key = None

            i += 1
            continue

        if ":" not in stripped:
            i += 1
            continue

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()

        parent_indent, parent_dict, _ = stack[-1]

        colon_pos = stripped.find(":")
        key = stripped[:colon_pos].strip().strip("'\"")
        val = stripped[colon_pos + 1 :].strip()

        anchor_name: str | None = None
        anchor_match = re.search(r"&(\w+)", val)
        if anchor_match:
            anchor_name = anchor_match.group(1)
            val = re.sub(r"&\w+", "", val).strip()

        alias_match = re.match(r"\*(\w+)", val)
        if alias_match:
            alias_name = alias_match.group(1)
            resolved = anchors.get(alias_name, {})
            parent_dict[key] = resolved
            i += 1
            continue

        val = val.strip("'\"")

        if val.endswith("|") or val.endswith(">"):
            style = "literal" if val.endswith("|") else "folded"
            val = val[:-1].strip().strip("'\"")
            multiline_lines: list[str] = []
            multiline_indent: int | None = None
            i += 1
            while i < len(lines):
                ml_line = lines[i]
                if multiline_indent is None:
                    if ml_line.strip() == "":
                        i += 1
                        continue
                    multiline_indent = len(ml_line) - len(ml_line.lstrip(" "))
                    if multiline_indent <= indent:
                        break
                else:
                    if ml_line.strip() == "":
                        multiline_lines.append("")
                        i += 1
                        continue
                    current_indent = len(ml_line) - len(ml_line.lstrip(" "))
                    if current_indent < multiline_indent:
                        break
                multiline_lines.append(ml_line.strip())
                i += 1

            combined = (
                "\n".join(multiline_lines) if style == "literal" else " ".join(multiline_lines)
            )
            parent_dict[key] = combined
            if anchor_name:
                anchors[anchor_name] = combined
            continue

        elif val == "":
            if anchor_name and anchor_name in anchors:
                parent_dict[key] = anchors[anchor_name]
                stack.append(
                    (indent, parent_dict[key] if isinstance(parent_dict[key], dict) else {}, None)
                )
            else:
                new_dict: dict[str, Any] = {}
                parent_dict[key] = new_dict
                stack.append((indent, new_dict, None))
                pending_list_key = None

            next_i = i + 1
            if next_i < len(lines):
                next_stripped = (
                    lines[next_i].split("#")[0].strip()
                    if "#" in lines[next_i]
                    else lines[next_i].strip()
                )
                if next_stripped.startswith("- "):
                    parent_dict[key] = [] if pending_list_key != key else parent_dict.get(key, [])
                    stack[-1] = (indent, parent_dict, key)
                    pending_list_key = key
            if anchor_name:
                anchors[anchor_name] = (
                    new_dict if isinstance(parent_dict.get(key), dict) else parent_dict[key]
                )
        else:
            coerced = _yaml_coerce(val)
            parent_dict[key] = coerced
            if anchor_name:
                anchors[anchor_name] = coerced

        i += 1

    return result


def load_config(root_dir: str | None = None) -> ConfigDict:
    """
    Load configuration from config.yaml/yml, .env, or bruno.json.

    Search order:
      1. config.yaml / config.yml
      2. .env
      3. bruno.json
      4. defaults
    """
    if root_dir is None:
        root_dir = os.getcwd()

    config = dict(DEFAULT_CONFIG)

    yaml_paths = [
        os.path.join(root_dir, "config.yaml"),
        os.path.join(root_dir, "config.yml"),
    ]
    for path in yaml_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    yaml_data = parse_yaml(f.read())
                    bruno_cfg = yaml_data.get("bruno") or yaml_data.get("BRUNO")
                    if isinstance(bruno_cfg, dict):
                        config["collection_path"] = bruno_cfg.get(
                            "collection_path", config["collection_path"]
                        )
                        config["collection_name"] = bruno_cfg.get(
                            "collection_name", config["collection_name"]
                        )
                        config["base_url"] = bruno_cfg.get("base_url", config["base_url"])
                    else:
                        if "BRUNO_COLLECTION_PATH" in yaml_data:
                            config["collection_path"] = yaml_data["BRUNO_COLLECTION_PATH"]
                        if "bruno_collection_path" in yaml_data:
                            config["collection_path"] = yaml_data["bruno_collection_path"]
                print_info(f"Loaded configuration from YAML: {os.path.basename(path)}")
                return config
            except Exception as e:
                print_warning(f"Error parsing YAML file {path}: {e}")

    env_path = os.path.join(root_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                env_data = parse_dotenv(f.read())
                if "BRUNO_COLLECTION_PATH" in env_data:
                    config["collection_path"] = env_data["BRUNO_COLLECTION_PATH"]
                if "BRUNO_COLLECTION_NAME" in env_data:
                    config["collection_name"] = env_data["BRUNO_COLLECTION_NAME"]
            print_info("Loaded configuration from .env")
            return config
        except Exception as e:
            print_warning(f"Error parsing .env: {e}")

    bruno_json_path = os.path.join(root_dir, "bruno.json")
    if os.path.exists(bruno_json_path):
        try:
            with open(bruno_json_path, "r", encoding="utf-8") as f:
                bjson = json.load(f)
                config["collection_path"] = root_dir
                config["collection_name"] = bjson.get("name", config["collection_name"])
            print_info("Current directory detected as active Bruno Collection")
            return config
        except Exception as e:
            print_warning(f"Error reading bruno.json: {e}")

    print_info(f"No custom configuration found. Using defaults (Path: {config['collection_path']})")
    return config


def resolve_collection_dir(project_root: str, collection_path: str) -> str:
    """Resolve collection path supporting ~, absolute, and project-relative paths."""
    expanded = os.path.expanduser(collection_path)
    if os.path.isabs(expanded):
        return os.path.abspath(expanded)
    return os.path.abspath(os.path.join(project_root, expanded))