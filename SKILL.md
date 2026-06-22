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

This skill includes a zero-dependency, installable Python package with a CLI command:

```
bruno-sync sync              # Scan codebase and sync .bru files
bruno-sync sync --dry-run    # Preview changes without writing
bruno-sync sync --prune      # Also remove orphaned .bru files
bruno-sync sync --dedup      # Remove duplicate .bru files
bruno-sync prune             # Standalone prune of orphaned files
bruno-sync add-endpoint --method POST --path /api/v1/users
```

Alternatively, for submodule/clone installs:
```bash
python3 scripts/sync_bruno.py sync
python3 scripts/sync_bruno.py sync --dry-run --verbose
python3 scripts/sync_bruno.py prune
```

### Verbosity Control

| Flag | Behavior |
|---|---|
| `-v` / `--verbose` | Show detailed debug output |
| `-q` / `--quiet` | Suppress all non-error output (ideal for CI) |

### Configuration

```bash
bruno-sync sync --config ./config.yaml     # Use YAML config
bruno-sync sync --env ./.env               # Use .env config
bruno-sync sync --project-root ./src       # Scan a subdirectory
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

1. **Scan Existing Collection First**: Before making any changes, scan the existing Bruno collection directory for current `.bru` files. Use `bruno-sync sync` only when you need to batch-detect routes from the codebase — do NOT run it blindly, as it may create unnecessary `_sync/` folders. Prefer to update or add individual `.bru` files directly when you know exactly which endpoints changed.

2. **Find Collection Path**: First look in the project's root `config.yaml` (or `config.yml`), then `.env` for the parameter `BRUNO_COLLECTION_PATH`. If not found, look for a `folder.bru` at the project root (the primary Bruno collection marker — its `meta.name` defines the collection name). If still not found, search subdirectories for `folder.bru` or `bruno.json`. Only fallback to a default `./bruno` directory as a last resort.

3. **Preserve User Modifications**: Do not overwrite the entire `.bru` file if it already exists! Preserve custom tests, scripting, headers, or query parameters that the developer has added.

4. **Organize Logically**: Mirror the codebase's folder structure inside the Bruno collection directory (e.g., `users/`, `auth/`, `payments/`) to keep the Bruno sidebar clean and readable. Reuse existing folder structures when adding new endpoints — do not create a parallel `_sync/` hierarchy unless the endpoint has no appropriate home.

5. **Ignore `_sync/` in Git**: Auto-generated `.bru` files are written to a `_sync/` folder inside the collection to keep them separate from hand-written files. **Always** add `_sync/` to your project's `.gitignore` to avoid committing auto-generated files. Example:
   ```bash
   echo "_sync/" >> .gitignore
   ```