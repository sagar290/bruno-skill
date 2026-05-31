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

# --- Codebase Route Scanner ---

def scan_file_for_routes(filepath):
    """
    Scans a single source file for API routing patterns across multiple stacks.
    Returns a list of dicts: [{'method': 'GET', 'path': '/api/v1/users'}]
    """
    routes = []
    _, ext = os.path.splitext(filepath)
    if ext not in ['.go', '.js', '.ts', '.py', '.rb', '.php', '.java']:
        return routes
        
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # 1. Match Go Gin / Chi / Fiber patterns: e.g. r.GET("/api/v1/users", handler)
        # Regex: \.(GET|POST|PUT|DELETE|PATCH|PATCH|OPTIONS|HEAD|Get|Post|Put|Delete|Patch|Options|Head)\(\s*["']([^"']+)["']
        go_pattern = r'\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|Get|Post|Put|Delete|Patch|Options|Head)\(\s*["\']([^"\']+)["\']'
        for match in re.finditer(go_pattern, content):
            method = match.group(1).upper()
            path = match.group(2)
            # Filter standard Go router functions that are not actual HTTP methods
            if method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']:
                routes.append({'method': method, 'path': path, 'source': filepath})
                
        # 2. Match standard Go http.HandleFunc / http.Handle: http.HandleFunc("/path", handler)
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

def sync_endpoint_to_bru(collection_dir, method, path, base_url, seq=1):
    """
    Creates or updates a .bru file, carefully merging and preserving
    headers, query parameters, auth, assertions, and custom tests.
    """
    method = method.upper()
    subfolder, filename = get_folder_and_filename(path, method)
    target_dir = os.path.join(collection_dir, subfolder)
    
    os.makedirs(target_dir, exist_ok=True)
    filepath = os.path.join(target_dir, filename)
    
    # 1. Define base meta block
    clean_name = f"{method} {path}"
    meta_block = f"  name: {clean_name}\n  type: http\n  seq: {seq}"
    
    # 2. Define URL parameters and path block
    url = f"{base_url}{path}"
    method_block = f"  url: {url}\n  body: none\n  auth: none"
    
    blocks = {}
    
    # 3. Read existing file if it exists to preserve developer edits
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                blocks = parse_bru_blocks(f.read())
            print_info(f"Updating existing endpoint file: {os.path.join(subfolder, filename)}")
        except Exception as e:
            print_warning(f"Error reading existing .bru file {filepath}, will recreate: {e}")
            
    # 4. Update core routing properties while preserving custom configurations
    blocks['meta'] = meta_block
    
    # Remove any old method blocks if HTTP method changed
    supported_methods = ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']
    for m in supported_methods:
        if m in blocks and m != method.lower():
            del blocks[m]
            
    # Set the current method block
    blocks[method.lower()] = method_block
    
    # Ensure path parameters are generated in the file if present in route (e.g. :id)
    path_params = re.findall(r'[:{]([a-zA-Z0-9_]+)}?', path)
    if path_params and 'params:path' not in blocks:
        param_lines = []
        for param in path_params:
            param_lines.append(f"  {param}: ")
        blocks['params:path'] = '\n'.join(param_lines)

    # 5. Write blocks back to file
    content = serialize_bru_blocks(blocks)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

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
            
    # Absolute path to collection
    collection_dir = os.path.abspath(os.path.join(project_root, cfg['collection_path']))
    
    if args.command == "sync":
        print_info(f"Scanning project files under {project_root}...")
        routes = scan_directory(project_root)
        print_info(f"Found {len(routes)} unique API endpoints.")
        
        if not routes:
            print_warning("No API endpoints were automatically detected. Make sure to define controllers/routes in your code.")
            # Initialize collection anyway to create the foundation
            initialize_collection(collection_dir, cfg['collection_name'])
            return
            
        initialize_collection(collection_dir, cfg['collection_name'])
        
        # Sync each endpoint to collection
        for idx, route in enumerate(routes, start=1):
            sync_endpoint_to_bru(
                collection_dir=collection_dir,
                method=route['method'],
                path=route['path'],
                base_url=cfg['base_url'],
                seq=idx
            )
            
        print_success(f"Synced {len(routes)} endpoints to Bruno collection at: {collection_dir}")
        
    elif args.command == "add-endpoint":
        initialize_collection(collection_dir, cfg['collection_name'])
        sync_endpoint_to_bru(
            collection_dir=collection_dir,
            method=args.method,
            path=args.path,
            base_url=cfg['base_url']
        )
        print_success(f"Successfully added manual endpoint: {args.method} {args.path}")

if __name__ == "__main__":
    main()
