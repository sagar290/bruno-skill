# Bruno Agent Skill

A Git-friendly, file-based API client integration skill for AI coding agents and human developers. 

This skill allows agents (like Antigravity, Cursor, Claude Code, or Cline) to automatically discover API routes in your codebase, generate or update Bruno (`.bru`) collection request files, and keep them synced with your VS Code/Cursor Bruno sidebar UI.

---

## How It Works

```
 ┌────────────────┐       ┌───────────────┐       ┌──────────────────┐
 │  API Codebase  │ ───>  │ sync_bruno.py │ ───>  │ Bruno Collection │
 │ (Go/Node/etc.) │       │  (CLI Sync)   │       │  (.bru files)    │
 └────────────────┘       └───────────────┘       └──────────────────┘
                                                            │
                                                            ▼
                                                  ┌──────────────────┐
                                                  │ VS Code Sidebar  │
                                                  │ (Live Rendering) │
                                                  └──────────────────┘
```

1.  **Code Scanner**: The sync script scans your codebase for routing definitions (supports Go, Node.js, Python, and others).
2.  **Configuration**: It reads the destination path from your `config.yaml`, `config.yml`, `.env`, or existing `bruno.json`.
3.  **Merge-Safe Generation**: It creates or updates `.bru` files in your collection directory. If you have customized headers, query parameters, or tests in VS Code, they are **fully preserved and merged**, not overwritten.
4.  **IDE Extension**: The VS Code/Cursor Bruno extension watches these files and updates your sidebar UI instantly.

---

## Directory Structure

*   `SKILL.md` — Root entry point containing YAML frontmatter and instructions for loading into the Antigravity SDK.
*   `scripts/sync_bruno.py` — Zero-dependency CLI script to manage the collection and scan routes.
*   `references/`
    *   `bruno_syntax.md` — Quick reference guide for Bruno request markup formats.
    *   `vscode_integration.md` — Guide on configuring and using the VS Code Bruno extension.
    *   `external_agents.md` — Custom prompts and instructions for Cursor, Claude, Copilot, and Cline.
*   `examples/`
    *   `config.yaml` / `sample.env` — Configuration templates.
    *   `cursorrules_example` — Template for Cursor auto-syncing.
    *   `sample_route.go` / `sample_route.js` — Sample code routers to test route discovery.

---

## Quickstart Guide

### Step 1: Add the Skill to Your Repository
Copy the `bruno` skill folder into a directory in your repository (e.g. `skills/bruno`).

### Step 2: Configure the Destination
Define your collection path and name in either your project's `config.yaml` or `.env` file:

**Option A: In `config.yaml`**
```yaml
bruno:
  collection_path: ./bruno
  collection_name: My Project API
  base_url: {{baseUrl}}
```

**Option B: In `.env`**
```env
BRUNO_COLLECTION_PATH=./bruno
BRUNO_COLLECTION_NAME=My Project API
```

### Step 3: Run the Synchronization
Run the sync script from your project root:

```bash
# Sync entire codebase routes to the collection directory
python3 skills/bruno/scripts/sync_bruno.py sync

# Sync specifying a custom config path
python3 skills/bruno/scripts/sync_bruno.py sync --config ./config.yaml
```

---

## Coding Agent Integration (Cursor, Claude, Cline)

To enable your coding agents to automatically maintain this collection whenever they write code, configure them to run the sync script:

### A. For Cursor & Cline / Roo-Code
Create a `.cursorrules` or `.clinerules` file in your project root containing:
```markdown
# Bruno API Syncing Rules
Whenever you create, delete, or modify an API endpoint/route in the codebase:
1. Run the sync command in the terminal (adjust path if needed):
   python3 skills/bruno/scripts/sync_bruno.py sync
2. Confirm in your response that the Bruno collection was successfully updated.
```

### B. For Claude Code CLI
Tell Claude Code in your prompt:
> *"Whenever you update any routes or controllers, run `python3 skills/bruno/scripts/sync_bruno.py sync` to keep my Bruno collection in sync."*

### C. For Google Antigravity SDK (In Python Code)
Load the skill directory when initializing your agent config:
```python
from google.antigravity import Agent, LocalAgentConfig

config = LocalAgentConfig(
    skills_paths=["./skills"] # Points to the parent folder of the 'bruno' skill
)
```

---

## Features & Customizations

*   **URL Variable Preserves**: Automatically detects path variables (e.g. `/users/:id` or `/users/{id}`) and generates empty input parameter slots in the request file.
*   **Logical Folders**: Subdirectories are generated based on route depth (e.g. `/api/v1/users` is saved in `api/v1/users-get.bru`), keeping the sidebar clean and organized.
*   **Merge Preservation**: Standard Javascript assertions, tests, pre-request scripts, headers, and request bodies are parsed out of existing files, saved, and merged back on subsequent syncs.
