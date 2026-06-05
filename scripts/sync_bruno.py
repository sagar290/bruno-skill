#!/usr/bin/env python3
"""
sync_bruno.py
Zero-dependency, multi-stack utility to sync API endpoints with Bruno collections.
Designed for both coding agents and human developers using VS Code / Cursor extensions.
"""

import os
import sys
import re
import json
import argparse

# --- Styling Helpers ---
def print_success(msg):
    print(f"\033[32m✔ {msg}\033[0m")

def print_info(msg):
    print(f"\033[34mℹ {msg}\033[0m")

def print_warning(msg):
    print(f"\033[33m⚠ {msg}\033[0m")

def print_error(msg):
    print(f"\033[31m✘ {msg}\033[0m", file=sys.stderr)

# --- Configuration Parsers ---

def parse_dotenv(content):
    """Parses environment variables from .env content."""
    config = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            config[key] = val
    return config

def parse_yaml(content):
    """
    Lightweight, robust YAML parser in pure Python.
    Handles nested key-values and basic typing without external dependencies.
    """
    result = {}
    lines = content.splitlines()
    stack = [(0, result)]
    
    for line in lines:
        # Strip comments
        line_clean = line.split('#')[0]
        stripped = line_clean.strip()
        if not stripped:
            continue
        if ':' not in stripped:
            continue
        
        # Determine indentation level
        indent = len(line_clean) - len(line_clean.lstrip(' '))
        
        key, val = [x.strip() for x in stripped.split(':', 1)]
        key = key.strip("'\"")
        val_clean = val.strip("'\"")
        
        # Pop stack to match current indentation level
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
            
        parent_indent, parent_dict = stack[-1]
        
        if val_clean == "":
            # Nested structure starts
            new_dict = {}
            parent_dict[key] = new_dict
            stack.append((indent, new_dict))
        else:
            # Parse primitives
            if val_clean.lower() == 'true':
                parent_dict[key] = True
            elif val_clean.lower() == 'false':
                parent_dict[key] = False
            elif val_clean.lower() == 'null' or val_clean == '~':
                parent_dict[key] = None
            else:
                try:
                    parent_dict[key] = int(val_clean)
                except ValueError:
                    try:
                        parent_dict[key] = float(val_clean)
                    except ValueError:
                        parent_dict[key] = val_clean
                        
    return result

def load_config(root_dir=None):
    """
    Loads destination configuration by looking for:
    1. config.yaml or config.yml
    2. .env
    3. bruno.json in root
    """
    if root_dir is None:
        root_dir = os.getcwd()
        
    config = {
        'collection_path': './bruno',
        'collection_name': 'Project API',
        'base_url': '{{baseUrl}}'
    }
    
    # 1. Check YAML config files
    yaml_paths = [os.path.join(root_dir, 'config.yaml'), os.path.join(root_dir, 'config.yml')]
    for path in yaml_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    yaml_data = parse_yaml(f.read())
                    # Check for nested bruno settings or top-level BRUNO_COLLECTION_PATH
                    bruno_cfg = yaml_data.get('bruno') or yaml_data.get('BRUNO')
                    if isinstance(bruno_cfg, dict):
                        config['collection_path'] = bruno_cfg.get('collection_path', config['collection_path'])
                        config['collection_name'] = bruno_cfg.get('collection_name', config['collection_name'])
                        config['base_url'] = bruno_cfg.get('base_url', config['base_url'])
                    else:
                        # Fallback to direct properties
                        if 'BRUNO_COLLECTION_PATH' in yaml_data:
                            config['collection_path'] = yaml_data['BRUNO_COLLECTION_PATH']
                        if 'bruno_collection_path' in yaml_data:
                            config['collection_path'] = yaml_data['bruno_collection_path']
                print_info(f"Loaded configuration from YAML: {os.path.basename(path)}")
                return config
            except Exception as e:
                print_warning(f"Error parsing YAML file {path}: {e}")
                
    # 2. Check Environment file
    env_path = os.path.join(root_dir, '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                env_data = parse_dotenv(f.read())
                if 'BRUNO_COLLECTION_PATH' in env_data:
                    config['collection_path'] = env_data['BRUNO_COLLECTION_PATH']
                if 'BRUNO_COLLECTION_NAME' in env_data:
                    config['collection_name'] = env_data['BRUNO_COLLECTION_NAME']
                print_info("Loaded configuration from .env")
                return config
        except Exception as e:
            print_warning(f"Error parsing .env: {e}")

    # 3. Check existing bruno.json
    bruno_json_path = os.path.join(root_dir, 'bruno.json')
    if os.path.exists(bruno_json_path):
        try:
            with open(bruno_json_path, 'r', encoding='utf-8') as f:
                bjson = json.load(f)
                config['collection_path'] = root_dir
                config['collection_name'] = bjson.get('name', config['collection_name'])
                print_info("Current directory detected as active Bruno Collection")
                return config
        except Exception as e:
            print_warning(f"Error reading bruno.json: {e}")
            
    print_info(f"No custom configuration found. Using defaults (Path: {config['collection_path']})")
    return config

def resolve_collection_dir(project_root, collection_path):
    """Resolve collection path supporting ~, absolute, and project-relative paths."""
    expanded = os.path.expanduser(collection_path)
    if os.path.isabs(expanded):
        return os.path.abspath(expanded)
    return os.path.abspath(os.path.join(project_root, expanded))

# --- Collection index (scan existing .bru files first) ---

AUTO_SYNC_FOLDER = '_sync'
COLLECTION_SKIP_DIRS = {'.git', 'node_modules', 'environments'}
HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']

def join_url_paths(*parts):
    segments = []
    for part in parts:
        if not part:
            continue
        segments.extend([p for p in part.strip('/').split('/') if p])
    return '/' + '/'.join(segments) if segments else '/'

def normalize_path(path):
    path = path.split('?')[0].strip()
    if not path.startswith('/'):
        path = '/' + path
    return re.sub(r'/+', '/', path).rstrip('/') or '/'

def extract_path_from_url(url):
    """Extract the URL path from a Bruno request URL (strips vars and host)."""
    path = re.sub(r'\{\{[^}]+\}\}', '', url).strip()
    if '://' in path:
        path = path.split('://', 1)[1]
        path = '/' + path.split('/', 1)[1] if '/' in path else '/'
    return normalize_path(path)

def extract_endpoint_from_bru(content):
    """Return (method, path) for an HTTP .bru file, or None."""
    blocks = parse_bru_blocks(content)
    meta = blocks.get('meta', '')
    meta_compact = re.sub(r'\s+', '', meta.lower())
    if 'type:http' not in meta_compact:
        return None

    for method in [m.lower() for m in HTTP_METHODS]:
        if method not in blocks:
            continue
        match = re.search(r'url:\s*(.+)', blocks[method])
        if match:
            return method.upper(), extract_path_from_url(match.group(1).strip())
    return None

def request_file_priority(filepath, collection_dir):
    """Prefer manually organized folders over auto-synced or root-level files."""
    rel = os.path.relpath(filepath, collection_dir).replace('\\', '/')
    score = rel.count('/')

    if rel.startswith(f'{AUTO_SYNC_FOLDER}/'):
        score -= 200
    elif '/' not in rel:
        score -= 100

    return score

def scan_collection(collection_dir):
    """
    Scan an existing Bruno collection and index requests by method + path.
    Returns (exact_index, all_entries) where all_entries supports suffix matching.
    """
    exact_index = {}
    exact_priority = {}
    all_entries = []

    if not os.path.isdir(collection_dir):
        return exact_index, all_entries

    for root, dirs, files in os.walk(collection_dir):
        dirs[:] = [d for d in dirs if d not in COLLECTION_SKIP_DIRS]
        for filename in files:
            if not filename.endswith('.bru') or filename == 'folder.bru':
                continue

            filepath = os.path.join(root, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    endpoint = extract_endpoint_from_bru(f.read())
                if not endpoint:
                    continue

                method, path = endpoint
                key = (method, path)
                priority = request_file_priority(filepath, collection_dir)
                if key not in exact_index or priority > exact_priority[key]:
                    exact_index[key] = filepath
                    exact_priority[key] = priority
                all_entries.append((method, path, filepath, priority))
            except Exception as e:
                print_warning(f"Could not index {filepath}: {e}")

    return exact_index, all_entries

def find_matching_file(method, path, exact_index, all_entries):
    """Find an existing .bru file for a route without reorganizing the collection."""
    norm = normalize_path(path)
    key = (method, norm)
    if key in exact_index:
        return exact_index[key]

    candidates = []
    for entry_method, entry_path, filepath, priority in all_entries:
        if entry_method != method:
            continue
        if entry_path == norm or entry_path.endswith(norm) or norm.endswith(entry_path):
            candidates.append((priority, len(entry_path), filepath))

    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]

# --- Codebase Route Scanner ---

def scan_go_file_for_routes(filepath):
    """Resolve Gin group prefixes so routes include full paths (e.g. /api/v1/auth/login)."""
    routes = []
    prefix_map = {}

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print_warning(f"Could not scan Go file {filepath}: {e}")
        return routes

    group_pattern = re.compile(r'(\w+)\s*:=\s*(\w+)\.Group\(\s*["\']([^"\']+)["\']')
    route_pattern = re.compile(
        r'(\w+)\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\(\s*["\']([^"\']+)["\']'
    )
    direct_route_pattern = re.compile(
        r'(router|engine|r)\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\(\s*["\']([^"\']+)["\']'
    )

    for line in lines:
        group_match = group_pattern.search(line)
        if group_match:
            var_name, parent_var, prefix = group_match.groups()
            parent_prefix = prefix_map.get(parent_var, '')
            prefix_map[var_name] = join_url_paths(parent_prefix, prefix)
            continue

        route_match = route_pattern.search(line)
        if route_match:
            var_name, method, path = route_match.groups()
            full_path = join_url_paths(prefix_map.get(var_name, ''), path)
            routes.append({'method': method.upper(), 'path': full_path, 'source': filepath})
            continue

        direct_match = direct_route_pattern.search(line)
        if direct_match:
            _, method, path = direct_match.groups()
            routes.append({'method': method.upper(), 'path': normalize_path(path), 'source': filepath})

    return routes

def scan_file_for_routes(filepath):
    """
    Scans a single source file for API routing patterns across multiple stacks.
    Returns a list of dicts: [{'method': 'GET', 'path': '/api/v1/users'}]
    """
    routes = []
    _, ext = os.path.splitext(filepath)
    if ext not in ['.go', '.js', '.ts', '.py', '.rb', '.php', '.java']:
        return routes

    if ext == '.go':
        return scan_go_file_for_routes(filepath)
        
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
                
        # 1. Match standard Go http.HandleFunc / http.Handle: http.HandleFunc("/path", handler)
        go_std_pattern = r'http\.HandleFunc\(\s*["\']([^"\']+)["\']'
        for match in re.finditer(go_std_pattern, content):
            routes.append({'method': 'GET', 'path': match.group(1), 'source': filepath})
            
        # 3. Express/NestJS routing patterns: app.get('/path', ...) or router.post('/path')
        express_pattern = r'(?:app|router|route)\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']'
        for match in re.finditer(express_pattern, content):
            method = match.group(1).upper()
            path = match.group(2)
            routes.append({'method': method, 'path': path, 'source': filepath})
            
        # 4. FastAPI/Flask decorator patterns: @app.get("/path") or @router.post("/path")
        py_decorator_pattern = r'@(?:app|router)\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']'
        for match in re.finditer(py_decorator_pattern, content):
            method = match.group(1).upper()
            path = match.group(2)
            routes.append({'method': method, 'path': path, 'source': filepath})
            
        # 5. Flask traditional: @app.route("/path", methods=["POST", "GET"])
        flask_route_pattern = r'@app\.route\(\s*["\']([^"\']+)["\'](?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?'
        for match in re.finditer(flask_route_pattern, content):
            path = match.group(1)
            methods_str = match.group(2)
            methods = ['GET']
            if methods_str:
                # parse methods string e.g. "POST", "GET"
                methods = [m.strip(' "\'') for m in methods_str.split(',')]
            for method in methods:
                routes.append({'method': method.upper(), 'path': path, 'source': filepath})
                
    except Exception as e:
        print_warning(f"Could not scan file {filepath}: {e}")
        
    return routes

def scan_directory(search_dir):
    """Recursively scans a directory for API route definitions."""
    all_routes = []
    exclude_dirs = {'.git', 'node_modules', 'vendor', 'bruno', 'bruno-collection', 'skills', '.gemini'}
    
    for root, dirs, files in os.walk(search_dir):
        # In-place modification to skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            filepath = os.path.join(root, file)
            file_routes = scan_file_for_routes(filepath)
            all_routes.extend(file_routes)
            
    # De-duplicate routes
    seen = set()
    unique_routes = []
    for r in all_routes:
        key = (r['method'], r['path'])
        if key not in seen:
            seen.add(key)
            unique_routes.append(r)
            
    return unique_routes

# --- Bruno (.bru) File Parser and Writer ---

def parse_bru_blocks(content):
    """
    Parses a .bru file into structured blocks, tracking brace balancing.
    Returns a dict: {block_name: block_content}
    """
    blocks = {}
    lines = content.splitlines()
    current_block = None
    block_lines = []
    brace_count = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if current_block is None:
            if stripped.endswith('{') and not line.startswith(' ') and not line.startswith('\t'):
                current_block = stripped.split('{')[0].strip()
                block_lines = []
                brace_count = 1
        else:
            brace_count += line.count('{')
            brace_count -= line.count('}')
            
            if brace_count == 0:
                # Finished parsing block
                blocks[current_block] = '\n'.join(block_lines)
                current_block = None
            else:
                block_lines.append(line)
        i += 1
        
    return blocks

def serialize_bru_blocks(blocks):
    """Serializes structured blocks back to .bru markup format."""
    # Standard ordering for elegant readable files
    block_order = [
        'meta',
        'get', 'post', 'put', 'delete', 'patch', 'options', 'head',
        'headers',
        'params:query',
        'params:path',
        'body:json',
        'body:text',
        'tests',
        'script:pre-request',
        'script:post-response'
    ]
    
    output = []
    written = set()
    
    for key in block_order:
        if key in blocks:
            output.append(f"{key} {{\n{blocks[key]}\n}}")
            written.add(key)
            
    # Catch-all for custom or unlisted blocks
    for key, val in blocks.items():
        if key not in written:
            output.append(f"{key} {{\n{val}\n}}")
            
    return '\n\n'.join(output) + '\n'

def make_safe_filename(path_str):
    """Generates a safe filename for a given URL path."""
    # Replace URL path parameters (e.g. :id or {id}) with safe text
    safe = path_str.replace(':', 'by-').replace('{', 'by-').replace('}', '')
    # Strip leading/trailing slashes and replace remaining with dash
    safe = safe.strip('/').replace('/', '-')
    if not safe:
        safe = "root"
    return safe.lower()

def get_folder_and_filename(path_str, method):
    """
    Determines the subdirectory and file name based on route structure.
    E.g. /api/v1/users -> Subdirectory: api/v1, Filename: users-get.bru
    """
    parts = [p for p in path_str.strip('/').split('/') if p]
    if len(parts) > 1:
        folder = os.path.join(*parts[:-1])
        base_name = parts[-1]
    else:
        folder = ""
        base_name = parts[0] if parts else "root"
        
    # Replace parameter notation for folder and files
    folder = folder.replace(':', '_').replace('{', '_').replace('}', '')
    base_name = base_name.replace(':', 'by-').replace('{', 'by-').replace('}', '').lower()
    
    filename = f"{base_name}-{method.lower()}.bru"
    return folder, filename

def sync_endpoint_to_bru(collection_dir, method, path, base_url, seq=1, existing_filepath=None):
    """
    Creates or updates a .bru file. When existing_filepath is set, only merges
    missing path params and preserves names, URLs, headers, body, and tests.
    New endpoints are added under _sync/ so manual folders stay untouched.
    """
    method = method.upper()
    path_params = re.findall(r'[:{]([a-zA-Z0-9_]+)}?', path)

    if existing_filepath:
        filepath = existing_filepath
        rel = os.path.relpath(filepath, collection_dir)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                blocks = parse_bru_blocks(f.read())
        except Exception as e:
            print_warning(f"Could not read existing file {rel}: {e}")
            return 'error'

        changed = False
        if path_params and 'params:path' not in blocks:
            blocks['params:path'] = '\n'.join(f"  {param}: " for param in path_params)
            changed = True

        if changed:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(serialize_bru_blocks(blocks))
            print_info(f"Updated existing request (preserved layout): {rel}")
            return 'updated'

        print_info(f"Preserved existing request (no changes): {rel}")
        return 'preserved'

    subfolder, filename = get_folder_and_filename(path, method)
    target_dir = os.path.join(collection_dir, AUTO_SYNC_FOLDER, subfolder)
    os.makedirs(target_dir, exist_ok=True)
    filepath = os.path.join(target_dir, filename)

    if os.path.exists(filepath):
        return sync_endpoint_to_bru(
            collection_dir, method, path, base_url, seq=seq, existing_filepath=filepath
        )

    clean_name = f"{method} {path}"
    meta_block = f"  name: {clean_name}\n  type: http\n  seq: {seq}"
    url = f"{base_url}{path}"
    method_block = f"  url: {url}\n  body: none\n  auth: none"

    blocks = {
        'meta': meta_block,
        method.lower(): method_block,
    }

    if path_params:
        blocks['params:path'] = '\n'.join(f"  {param}: " for param in path_params)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(serialize_bru_blocks(blocks))

    rel = os.path.relpath(filepath, collection_dir)
    print_info(f"Added new request: {rel}")
    return 'added'

# --- Collection Management ---

def initialize_collection(collection_dir, collection_name):
    """Creates a bruno.json file at the collection root if not present."""
    os.makedirs(collection_dir, exist_ok=True)
    bruno_json_path = os.path.join(collection_dir, 'bruno.json')
    
    if not os.path.exists(bruno_json_path):
        bjson = {
            "version": "1",
            "name": collection_name,
            "type": "collection",
            "ignore": [
                "node_modules",
                ".git"
            ]
        }
        with open(bruno_json_path, 'w', encoding='utf-8') as f:
            json.dump(bjson, f, indent=2)
        print_success(f"Initialized new Bruno Collection '{collection_name}' at {collection_dir}")
    else:
        print_info(f"Existing Bruno Collection detected at {collection_dir}")

# --- CLI Controller ---

def main():
    parser = argparse.ArgumentParser(
        description="Bruno Collection Sync Tool - Automate .bru file management across stack codebases."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Scan codebase and sync to Bruno Collection")
    sync_parser.add_argument("--config", help="Path to config.yaml configuration file")
    sync_parser.add_argument("--env", help="Path to .env configuration file")
    sync_parser.add_argument("--project-root", default=".", help="Root directory of the project to scan")
    
    # Add Endpoint command
    add_parser = subparsers.add_parser("add-endpoint", help="Manually append an endpoint to the collection")
    add_parser.add_argument("--method", required=True, help="HTTP method (GET, POST, etc.)")
    add_parser.add_argument("--path", required=True, help="Endpoint request path (e.g. /api/users)")
    add_parser.add_argument("--name", help="Optional name for the request")
    add_parser.add_argument("--config", help="Path to config.yaml configuration file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    # Resolve config
    project_root = os.path.abspath(args.project_root if hasattr(args, 'project_root') else ".")
    cfg = load_config(project_root)
    
    # Override config using command-line arguments if provided
    if hasattr(args, 'config') and args.config:
        if os.path.exists(args.config):
            with open(args.config, 'r', encoding='utf-8') as f:
                ycfg = parse_yaml(f.read())
                bruno_c = ycfg.get('bruno') or ycfg.get('BRUNO') or ycfg
                if isinstance(bruno_c, dict):
                    cfg['collection_path'] = bruno_c.get('collection_path', cfg['collection_path'])
                    cfg['collection_name'] = bruno_c.get('collection_name', cfg['collection_name'])
                    cfg['base_url'] = bruno_c.get('base_url', cfg['base_url'])
        else:
            print_error(f"Config file not found: {args.config}")
            sys.exit(1)
            
    if hasattr(args, 'env') and args.env:
        if os.path.exists(args.env):
            with open(args.env, 'r', encoding='utf-8') as f:
                ecfg = parse_dotenv(f.read())
                if 'BRUNO_COLLECTION_PATH' in ecfg:
                    cfg['collection_path'] = ecfg['BRUNO_COLLECTION_PATH']
                if 'BRUNO_COLLECTION_NAME' in ecfg:
                    cfg['collection_name'] = ecfg['BRUNO_COLLECTION_NAME']
        else:
            print_error(f"Env file not found: {args.env}")
            sys.exit(1)
            
    collection_dir = resolve_collection_dir(project_root, cfg['collection_path'])
    
    if args.command == "sync":
        initialize_collection(collection_dir, cfg['collection_name'])

        print_info(f"Scanning existing Bruno collection at {collection_dir}...")
        exact_index, all_entries = scan_collection(collection_dir)
        print_info(f"Indexed {len(all_entries)} existing HTTP requests in collection.")

        print_info(f"Scanning project files under {project_root}...")
        routes = scan_directory(project_root)
        print_info(f"Found {len(routes)} unique API endpoints in codebase.")

        if not routes:
            print_warning("No API endpoints were automatically detected. Existing collection was left unchanged.")
            return

        stats = {'preserved': 0, 'updated': 0, 'added': 0, 'error': 0}

        for idx, route in enumerate(routes, start=1):
            existing_filepath = find_matching_file(
                route['method'], route['path'], exact_index, all_entries
            )
            result = sync_endpoint_to_bru(
                collection_dir=collection_dir,
                method=route['method'],
                path=route['path'],
                base_url=cfg['base_url'],
                seq=idx,
                existing_filepath=existing_filepath,
            )
            stats[result] = stats.get(result, 0) + 1

        print_success(
            f"Sync complete at {collection_dir}: "
            f"{stats.get('preserved', 0)} preserved, "
            f"{stats.get('updated', 0)} updated, "
            f"{stats.get('added', 0)} added to {AUTO_SYNC_FOLDER}/, "
            f"{stats.get('error', 0)} errors"
        )
        print_info("Manual folders and requests were not removed or reorganized.")
        
    elif args.command == "add-endpoint":
        initialize_collection(collection_dir, cfg['collection_name'])
        exact_index, all_entries = scan_collection(collection_dir)
        existing_filepath = find_matching_file(
            args.method.upper(), args.path, exact_index, all_entries
        )
        result = sync_endpoint_to_bru(
            collection_dir=collection_dir,
            method=args.method,
            path=args.path,
            base_url=cfg['base_url'],
            existing_filepath=existing_filepath,
        )
        print_success(f"Endpoint {args.method} {args.path} — {result}")

if __name__ == "__main__":
    main()
