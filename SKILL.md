---
name: bruno
description: "Equips agents with capabilities to discover, create, update, and manage Bruno file-based API collections. Fully integrates with config.yaml, .env, and VS Code/Cursor Bruno extensions."
---

# Bruno Integration Skill

Bruno is a Git-friendly, file-based API client that stores collections directly in your repository as standard markup files (`.bru`). This skill allows AI agents and developers to collaborate seamlessly on API testing and development.

Since Bruno stores all requests as simple text files, any changes or additions made by an agent are instantly reflected in the developer's VS Code or Cursor Bruno extensions.

---

## Capabilities & Workflows

1. **Auto-Discovery of API Routes**: Automatically analyze codebases (Go/Gin/Chi/mux, Express/Fastify/Koa, Next.js, Flask/FastAPI, Spring Boot, Rails, Laravel, and more) to discover endpoints.
2. **Synchronized State**: Read project configurations (`.env`, `config.yaml`, `config.yml`, or `bruno.json`) to find the Bruno collection folder and automatically generate or update `.bru` request files.
3. **Harmonious Merging**: Ensure that when endpoints are updated, manually created headers, parameters, and Javascript assertions/tests in the `.bru` files are carefully merged and preserved.
4. **Git-Friendly API Management**: Store and commit API collections in version control alongside the source code.

---

## Route Sync Utility

This skill includes a zero-dependency Python package with a CLI:

```bash
python3 scripts/sync_bruno.py sync              # Scan codebase and sync .bru files
python3 scripts/sync_bruno.py sync --dry-run    # Preview changes without writing
python3 scripts/sync_bruno.py sync --prune      # Also remove orphaned .bru files
python3 scripts/sync_bruno.py sync --dedup      # Remove duplicate .bru files
python3 scripts/sync_bruno.py prune             # Standalone prune of orphaned files
python3 scripts/sync_bruno.py add-endpoint --method POST --path /api/v1/users
```

If installed locally via `pip install -e .`, the `bruno-sync` command is also available:

```bash
bruno-sync sync
bruno-sync sync --dry-run
bruno-sync sync --prune
```

### Verbosity Control

| Flag | Behavior |
|---|---|
| `-v` / `--verbose` | Show detailed debug output |
| `-q` / `--quiet` | Suppress all non-error output (ideal for CI) |

### Configuration

```bash
python3 scripts/sync_bruno.py sync --config ./config.yaml     # Use YAML config
python3 scripts/sync_bruno.py sync --env ./.env               # Use .env config
python3 scripts/sync_bruno.py sync --project-root ./src       # Scan a subdirectory
```

---

## Routing Table & References

Use these documents to understand specific aspects of Bruno files and their integration:

### References
* **Bruno Markup Syntax Guide**: Learn the layout, syntax, and scripting structure of `.bru` files. Read [bruno_syntax.md](references/bruno_syntax.md).
* **VS Code / Cursor Integration Guide**: Learn how to utilize the Bruno extension for instant collaboration. Read [vscode_integration.md](references/vscode_integration.md).
* **External Coding Agents Guide**: Learn how to configure Cursor, Copilot, Cline, or OpenCode to use this skill. Read [external_agents.md](references/external_agents.md).

### Examples
* **Configuration Templates**: Learn how to specify collection paths in `config.yaml` or `.env`. View [config.yaml](examples/config.yaml) and [sample.env](examples/sample.env).
* **Cursor Integration Templates**: Learn how to automatically trigger the skill in Cursor using a `.cursorrules` configuration. View [cursorrules_example](examples/cursorrules_example).
* **Sample Code Routers**: Check out how the sync script identifies API routes across different language stacks. View Go Router [sample_route.go](examples/sample_route.go) and Node.js Router [sample_route.js](examples/sample_route.js).

---

## Agent Instructions & Rules

When you are acting as an agent working on a project with this skill:

1. **Detect API Modifications**: Whenever you create or modify an API endpoint in the codebase (e.g. adding a new controller, modifying route parameters, changing methods), you **MUST** automatically trigger `python3 scripts/sync_bruno.py sync` or manually update the corresponding `.bru` files.
2. **Find Collection Path**: First look in the project's root `config.yaml` (or `config.yml`), then `.env` for the parameter `BRUNO_COLLECTION_PATH`. If not found, look for `bruno.json` or fallback to a default `./bruno` directory.
3. **Preserve User Modifications**: Do not overwrite the entire `.bru` file if it already exists! Preserve custom tests, scripting, headers, or query parameters that the developer has added.
4. **Organize Logically**: Mirror the codebase's folder structure inside the Bruno collection directory (e.g., `users/`, `auth/`, `payments/`) to keep the Bruno sidebar clean and readable.