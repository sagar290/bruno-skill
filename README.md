# Bruno Agent Skill

Auto-generate and sync Bruno `.bru` API collection files from your codebase.

## How It Works

When you run `bruno-sync sync`, the tool goes through these steps:

### 1. Load Config

Reads configuration from `config.yaml` → `.env` → `bruno.json` → defaults. Gets `collection_path`, `collection_name`, and `base_url`.

### 2. Initialize

- Creates `bruno.json` at the collection root if it doesn't exist
- Appends `_sync/` to your project's `.gitignore` if missing (so auto-generated files aren't committed)
- Scans all existing `.bru` files in the collection and builds an index of `(method, path) → filepath`

### 3. Scan Codebase

Walks your project directory (skipping `.git`, `node_modules`, `vendor`, `_sync`, etc.) and dispatches each source file to a language-specific scanner:

| Extension | Scanners |
|---|---|
| `.go` | Gin, Chi, gorilla/mux |
| `.js` / `.ts` / `.jsx` / `.tsx` | Express, Fastify, Koa, Next.js App Router |
| `.py` | Flask, FastAPI |
| `.java` | Spring Boot (@RequestMapping, @GetMapping, etc.) |
| `.rb` | Rails (resources, verb routes) |
| `.php` | Laravel (Route::get, apiResource, prefix groups, match/any) |

Output: a deduplicated list of `{method, path, source}` — e.g. `{method: "GET", path: "/api/v1/users", source: "routes.go:12"}`

### 4. Sync Each Route

For every scanned route, the tool checks if a `.bru` file already exists:

- **Already exists** → merge-only: adds missing path params, preserves all your custom headers, tests, auth, and scripts untouched
- **Doesn't exist** → creates a new file under `collection/_sync/`:
  ```
  /api/v1/users/:id GET → collection/_sync/api/v1/users-by-id-get.bru
  ```

### 5. Optional Cleanup

| Flag | What it does |
|---|---|
| `--prune` | Delete `.bru` files in `_sync/` whose routes no longer exist in the codebase |
| `--dedup` | Delete lower-priority duplicates (manual folders win over `_sync/` over root-level) |
| `--dry-run` | Preview all changes without writing or deleting anything |

### Key Design Choices

- **`_sync/` isolation** — auto-generated files live in `_sync/`, never overwriting your hand-written `.bru` files. Manual files always win in merge priority.
- **Merge-safe** — only missing path params are added to existing files. Headers, tests, auth, and scripts are never overwritten.
- **Auto gitignore** — `_sync/` is appended to `.gitignore` automatically so you don't accidentally commit generated files.
- **Zero dependencies** — pure Python stdlib, no pip packages required at runtime.

## Installation

**Git Submodule (recommended):**
```bash
git submodule add git@github.com:sagar290/bruno-skill.git skills/bruno
```

**Direct Clone:**
```bash
git clone git@github.com:sagar290/bruno-skill.git skills/bruno
rm -rf skills/bruno/.git
```

**Local development install (optional, for the CLI command):**
```bash
cd skills/bruno
pip install -e .
```

## Usage

```bash
# Sync all endpoints
python3 skills/bruno/scripts/sync_bruno.py sync

# Preview changes without writing
python3 skills/bruno/scripts/sync_bruno.py sync --dry-run

# Verbose / quiet output
python3 skills/bruno/scripts/sync_bruno.py -v sync
python3 skills/bruno/scripts/sync_bruno.py -q sync

# Prune orphaned .bru files
python3 skills/bruno/scripts/sync_bruno.py prune

# Add a single endpoint
python3 skills/bruno/scripts/sync_bruno.py add-endpoint --method POST --path /api/v1/users --name "Create User"

# Specify config
python3 skills/bruno/scripts/sync_bruno.py sync --config ./config.yaml
python3 skills/bruno/scripts/sync_bruno.py sync --env ./.env
```

If installed via `pip install -e .`, the `sync_bruno.py` script also exposes a `bruno-sync` CLI command:
```bash
bruno-sync sync
bruno-sync sync --dry-run --verbose
bruno-sync prune
```

## Configuration

Add to `config.yaml`:
```yaml
bruno:
  collection_path: ./bruno
  collection_name: My Project API
  base_url: "{{baseUrl}}"
```

Or add to `.env`:
```env
BRUNO_COLLECTION_PATH=./bruno
BRUNO_COLLECTION_NAME=My Project API
```

## Agent Integration

**Cursor / Cline** — add to `.cursorrules` or `.clinerules`:
```
When you create, delete, or modify an API endpoint, run:
python3 skills/bruno/scripts/sync_bruno.py sync
```

**Claude Code** — include in your prompt:
> Whenever you update routes, run `python3 skills/bruno/scripts/sync_bruno.py sync`

**Antigravity SDK:**
```python
from google.antigravity import Agent, LocalAgentConfig

config = LocalAgentConfig(skills_paths=["./skills"])
```

## Supported Frameworks

| Language | Frameworks |
|---|---|
| Go | Gin, Chi, gorilla/mux, stdlib net/http |
| JavaScript/TypeScript | Express, Fastify, Koa, Next.js App Router |
| Python | Flask, FastAPI |
| Java | Spring Boot (@RequestMapping, @GetMapping, etc.) |
| Ruby | Rails (resources, verb routes) |
| PHP | Laravel (Route::get, apiResource, prefix groups, match/any) |

## CLI Reference

| Command | Description |
|---|---|
| `sync` | Scan codebase and sync to Bruno collection |
| `sync --dry-run` | Preview what would change without writing |
| `sync --prune` | Remove orphaned .bru files for deleted routes |
| `sync --dedup` | Remove duplicate .bru files for the same endpoint |
| `add-endpoint` | Manually add a single endpoint |
| `prune` | Standalone prune of orphaned .bru files |
| `-v` / `--verbose` | Show detailed debug output |
| `-q` / `--quiet` | Suppress all non-error output |

## Directory Structure

```
bruno_sync/           # Python package source
  __init__.py         # Package metadata
  cli.py              # CLI entry point
  parsers.py          # YAML, dotenv, config loaders
  bru.py              # .bru file parser/writer
  collection.py       # Sync, prune, dedup logic
  scanner.py          # Directory scanner dispatcher
  log.py              # Styled output with verbosity levels
  scanners/           # Language-specific route scanners
    go.py             # Gin, Chi, gorilla/mux
    java.py           # Spring Boot
    javascript.py     # Express, Fastify, Koa, Next.js
    php.py            # Laravel
    python.py         # Flask, FastAPI
    ruby.py           # Rails
scripts/
  sync_bruno.py      # Entry point (python3 scripts/sync_bruno.py ...)
tests/
  test_sync_bruno.py # 77 unit & integration tests
references/          # Bruno syntax, VS Code integration guides
examples/            # Config templates and sample routes
```

## Features

- **Multi-framework scanning** — Gin, Chi, gorilla/mux, Express, Fastify, Koa, Next.js, Flask, FastAPI, Spring Boot, Rails, Laravel
- **Path variables** — auto-detects `/users/:id` and `/users/{id}` patterns
- **Logical folders** — routes grouped by path depth (e.g. `api/v1/users-get.bru`)
- **Merge-safe** — preserves your custom headers, tests, and scripts on re-sync
- **Prune** — removes orphaned `.bru` files for deleted routes (`--prune`)
- **Dedup** — cleans up duplicate `.bru` files (`--dedup`)
- **Dry-run** — preview all changes before writing (`--dry-run`)
- **Verbose/quiet** — `-v` for debug output, `-q` for CI silence