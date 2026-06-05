# Bruno Agent Skill

Auto-generate and sync Bruno `.bru` API collection files from your codebase.

## How It Works

1. Scan your codebase for route definitions (Go, Node.js, Python, etc.)
2. Generate/update `.bru` files in your Bruno collection
3. Existing custom headers, tests, and scripts are preserved on sync
4. VS Code Bruno extension picks up changes instantly

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

## Configuration

Add to `config.yaml`:
```yaml
bruno:
  collection_path: ./bruno
  collection_name: My Project API
  base_url: {{baseUrl}}
```

Or add to `.env`:
```env
BRUNO_COLLECTION_PATH=./bruno
BRUNO_COLLECTION_NAME=My Project API
```

## Usage

```bash
python3 skills/bruno/scripts/sync_bruno.py sync
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

## Directory Structure

- `SKILL.md` — Skill entry point for Antigravity SDK
- `scripts/sync_bruno.py` — CLI sync script
- `references/` — Bruno syntax, VS Code integration, and agent guides
- `examples/` — Config templates and sample routes

## Features

- **Path variables** — auto-detects `/users/:id` and `/users/{id}` patterns
- **Logical folders** — routes grouped by path depth (e.g. `api/v1/users-get.bru`)
- **Merge-safe** — preserves your custom headers, tests, and scripts on re-sync
