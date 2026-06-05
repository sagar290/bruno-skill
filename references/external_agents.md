# External Coding Agents Integration Guide (Cursor, Copilot, Cline, OpenCode)

When developers use LLM-based coding assistants inside their editors—such as **Cursor (Composer / Agent Mode)**, **GitHub Copilot**, **Cline (Roo-Code)**, or **OpenCode**—they can easily equip these agents with the Bruno skill.

Since these assistants can read workspace files and execute terminal commands, the Bruno skill works out-of-the-box by combining:
1.  **System Prompts / Rules**: Guiding the AI on when and how to manage the collection.
2.  **Terminal Automation**: Allowing the AI to invoke `python3 scripts/sync_bruno.py sync` automatically.

---

## 1. How to Equip Your IDE Agent with Bruno Rules

To ensure your editor's coding agent automatically maintains your Bruno collection, add instructions to your editor's system rules.

### For Cursor & Cursor Composer
Create or append to the `.cursorrules` file at the root of your project:

```markdown
# Bruno API Syncing Rules
Whenever you create, delete, or modify an API endpoint/route in the codebase:
1. You MUST synchronize the Bruno API collection immediately.
2. Check if a `config.yaml` or `.env` is available to locate the collection path (e.g. `BRUNO_COLLECTION_PATH`).
3. Run the following CLI command in the terminal to perform the synchronization:
    python3 skills/bruno/scripts/sync_bruno.py sync
4. Do not overwrite or delete custom tests, headers, or query parameters in existing .bru files; the sync script will safely merge them.
```

If installed locally via `pip install -e .`, you can also use `bruno-sync sync`.

### For Cline / Roo-Code / OpenCode
Create a `.clinerules` or `.copilotinstructions` file in your root workspace containing the same markdown rules as above.

---

## 2. Command Reference for Coding Agents

When your agent needs to interact with the Bruno collection, it can use these CLI commands directly:

### Syncing the Collection (Main Action)
Whenever the agent makes route updates:
```bash
python3 skills/bruno/scripts/sync_bruno.py sync
python3 skills/bruno/scripts/sync_bruno.py sync --dry-run --verbose
```

### Pruning Orphaned Files
Remove `.bru` files for routes that no longer exist in the codebase:
```bash
python3 skills/bruno/scripts/sync_bruno.py prune
```

### Appending an Endpoint Manually
If the agent is designing a new endpoint that hasn't been implemented in code yet:
```bash
python3 skills/bruno/scripts/sync_bruno.py add-endpoint --method POST --path /api/v1/login --name "User Login"
```

### Deduplicating Files
If duplicate `.bru` files have accumulated:
```bash
python3 skills/bruno/scripts/sync_bruno.py sync --dedup
```

---

## 3. Standard Prompts for Developers

As a developer, you can issue direct prompts to your coding agents to utilize this skill:

*   **Prompt**: *"Add a new POST route for user registration in our backend, and then sync my Bruno collection so I can test it."*
*   **Prompt**: *"Refactor the path parameter from `:id` to `:userId` in our router, and sync the changes to Bruno. Ensure my custom tests in VS Code are preserved."*
*   **Prompt**: *"Look at our API codebase and generate a brand-new Bruno collection under `./bruno-api`."*