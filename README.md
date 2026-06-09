# google-drive-files-mcp

<!-- mcp-name: io.github.zayansalman/google-drive-files-mcp -->

A focused [Model Context Protocol](https://modelcontextprotocol.io) server (and standalone CLI) for **moving and organizing** files in Google Drive — move files/folders between folders and create folders. Three tools, no destructive operations.

Built because the hosted Google Drive connectors can search, read, and **copy** files, but cannot **move** them — `copy` duplicates a file (new ID) rather than relocating it. This server adds a true move (`files.update` changing parents) plus folder creation, for any MCP client (Claude Code, Claude Desktop, Cursor, Cline, etc.).

## Tools

- `drive_search(query, only_folders=False, max_results=20)` — find files/folders (and their IDs) to move or to use as destinations.
- `drive_create_folder(name, parent=None)` — create a folder (`parent` accepts an ID, URL, `root`, or an unambiguous folder name).
- `drive_move(file, dest_folder, keep_existing_parents=False)` — move a file/folder into a destination. By default it's a *true move* (removed from its current folder); set `keep_existing_parents=True` to add it to the destination without removing it from where it already lives.

No rename, copy, trash, or delete — this tool is deliberately limited to non-destructive organizing. (`copy` already exists in the hosted Drive connector.)

## Scope warning (read this)

Moving an existing arbitrary file requires the **full `drive` scope** — read/write/delete on **all** your Drive files. There is no narrower scope that can change a file's parents (`drive.file` only covers files the app itself created). This tool is therefore far more powerful than a read-only connector. Treat its cached token like a password (stored `0600`), and prefer an isolated OAuth client/token rather than sharing one with read-only tools.

## Install

```bash
pip install google-drive-files-mcp
# or: uv tool install google-drive-files-mcp
```

## One-time setup (~10 min)

1. [Google Cloud Console](https://console.cloud.google.com/) → create/pick a project.
2. Enable the Drive API: [console.cloud.google.com/apis/library/drive.googleapis.com](https://console.cloud.google.com/apis/library/drive.googleapis.com).
3. OAuth consent screen → **Internal** (Workspace; no verification needed even for the restricted full-drive scope) or **External** + add yourself as a test user (personal Gmail).
4. Credentials → **OAuth client ID** → **Desktop app** → download JSON.
5. `google-drive-files-mcp setup --import-credentials ~/Downloads/client_secret_*.json` → consent in the browser.

Verify:
```bash
google-drive-files-mcp status
google-drive-files-mcp search "Reports" --folders
```

## Claude Code

```bash
claude mcp add --scope user google-drive-files google-drive-files-mcp -- serve
```

> Find my "Q2 Report" doc and move it into the "2026 Reports" folder.

## Claude Desktop

```json
{
  "mcpServers": {
    "google-drive-files": { "command": "google-drive-files-mcp", "args": ["serve"] }
  }
}
```

## CLI

```bash
google-drive-files-mcp search "budget"                 # find a file + its ID
google-drive-files-mcp search "Reports" --folders      # find destination folders
google-drive-files-mcp mkdir "2026 Reports"            # create a folder
google-drive-files-mcp move <file-url-or-id> "2026 Reports"   # move into it (by folder name)
google-drive-files-mcp move <file-url-or-id> root      # move back to My Drive root
```

`drive_move` returns the before/after parents so the move is auditable:
```json
{ "id": "1Abc…", "name": "Q2 Report", "moved_from": ["0OldFolderId"], "moved_to": "1NewFolderId", "parents_now": ["1NewFolderId"], "web_view_link": "https://docs.google.com/…" }
```

## Configuration

| Variable | Default | What |
|---|---|---|
| `GDRIVE_FILES_MCP_CREDENTIALS` | `~/.config/google-drive-files-mcp/credentials.json` | OAuth client secret |
| `GDRIVE_FILES_MCP_TOKEN` | `~/.config/google-drive-files-mcp/token.json` | Cached refresh token |
| `GDRIVE_FILES_MCP_SCOPES` | `https://www.googleapis.com/auth/drive` | OAuth scopes (comma-separated) |

## Safety notes

- **True move removes the file from its current folder.** Drive items can have multiple parents; `keep_existing_parents=True` adds without removing.
- **Folder-name destinations must be unambiguous.** If two folders share a name, `drive_move` refuses and lists the candidates so you can pass an explicit ID.
- **The before/after parents are returned** on every move so an agent (or you) can verify the result.

## License

MIT. See [LICENSE](LICENSE).
