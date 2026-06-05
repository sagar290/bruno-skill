# Bruno Agent Skill

Auto-generate and sync Bruno `.bru` API collection files from your codebase.

## How It Works

1. Scan your codebase for route definitions (Go/Gin/Chi/mux, Express/Fastify/Koa, Next.js, Flask/FastAPI, Spring Boot, Rails, etc.)
2. Generate/update `.bru` files in your Bruno collection
3. Existing custom headers, tests, and scripts are preserved on sync
4. VS Code Bruno extension picks up changes instantly

## Installation

**pip install (recommended for standalone use):**
```bash
pip install -e .
# or from a remote repo:
# pip install git+https://github.com/sagar290/bruno-skill.git
```

This exposes the `bruno-sync` CLI command globally.

**Git Submodule (for monorepo skill use):**
```bash
git submodule add git@github.com:sagar290/bruno-skill.git skills/bruno
```

**Direct Clone:**
```bash
git clone git@github.com:sagar290/bruno-skill.git skills/bruno
rm -rf skills/bruno/.git
```

## Usage

### Installed via pip

```bash
# Sync all endpoints
bruno-sync sync

# Preview changes without writing
bruno-sync sync --dry-run

# Verbose / quiet output
bruno-sync -v sync
bruno-sync -q sync

# Prune orphaned .bru files
bruno-sync prune

# Add a single endpoint
bruno-sync add-endpoint --method POST --path /api/v1/users --name "Create User"

# Specify config
bruno-sync sync --config ./config.yaml
bruno-sync sync --env ./.env
```

### Using the script directly (submodule / clone)

```bash
python3 skills/bruno/scripts/sync_bruno.py sync
python3 skills/bruno/scripts/sync_bruno.py sync --dry-run --verbose
python3 skills/bruno/scripts/sync_bruno.py prune
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
bruno-sync sync
```

**Claude Code** — include in your prompt:
> Whenever you update routes, run `bruno-sync sync`

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
bruno_sync/           # Installable Python package
  __init__.py         # Package metadata
  cli.py              # CLI entry point (bruno-sync command)
  parsers.py          # YAML, dotenv, config loaders
  bru.py              # .bru file parser/writer
  collection.py       # Sync, prune, dedup logic
  scanner.py          # Directory scanner dispatcher
  log.py              # Styled output with verbosity levels
  scanners/           # Language-specific route scanners
    go.py             # Gin, Chi, gorilla/mux
    java.py           # Spring Boot
    javascript.py     # Express, Fastify, Koa, Next.js
    python.py         # Flask, FastAPI
    ruby.py           # Rails
scripts/
  sync_bruno.py      # Backward-compatible entry point
tests/
  test_sync_bruno.py # 67 unit & integration tests
references/          # Bruno syntax, VS Code integration guides
examples/            # Config templates and sample routes
```

## Features

- **Multi-framework scanning** — Gin, Chi, gorilla/mux, Express, Fastify, Koa, Next.js, Flask, FastAPI, Spring Boot, Rails
- **Path variables** — auto-detects `/users/:id` and `/users/{id}` patterns
- **Logical folders** — routes grouped by path depth (e.g. `api/v1/users-get.bru`)
- **Merge-safe** — preserves your custom headers, tests, and scripts on re-sync
- **Prune** — removes orphaned `.bru` files for deleted routes (`--prune`)
- **Dedup** — cleans up duplicate `.bru` files (`--dedup`)
- **Dry-run** — preview all changes before writing (`--dry-run`)
- **Verbose/quiet** — `-v` for debug output, `-q` for CI silence