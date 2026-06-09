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

## Troubleshooting

**`HttpError 403: Google Drive API has not been used in project … or it is disabled`**
Enable the Drive API on the project that owns your OAuth client: [console.cloud.google.com/apis/library/drive.googleapis.com](https://console.cloud.google.com/apis/library/drive.googleapis.com) → **Enable**, then wait ~1 min and retry. (This is the single most common first-run error.)

**`multiple folders named '…'; pass the folder ID/URL instead`**
Two or more of your folders share that name, so a name is ambiguous. Run `google-drive-files-mcp search "<name>" --folders` to get the IDs and pass the exact one.

**`no folder named '…' found`**
Create it first (`google-drive-files-mcp mkdir "<name>"`) or pass a folder ID/URL/`root`.

**`HttpError 403: insufficientFilePermissions` when moving**
Either the token lacks the full `drive` scope — re-authorize with `google-drive-files-mcp setup --reauth` — or you don't have edit rights on the file/destination (you can't move a file someone else owns unless they've granted you edit access).

**`No valid Google token` from Claude Desktop / cron**
The first consent needs a browser. Run `google-drive-files-mcp setup` once in a terminal; later headless runs reuse and auto-refresh the cached token.

**A move "removed" a file from a shared folder unexpectedly**
A true move removes the item from its current parent(s). If you meant to *also* keep it where it was, use `keep_existing_parents=true` (CLI `--keep`).

## Use it from other clients (Cursor, Cline, Continue, …)

Any stdio MCP client works — see [docs/other-clients.md](docs/other-clients.md).

## Authentication — bring your own Google OAuth client

There are **no API keys and no shipped secrets**. The server authenticates to *your* Google account with an OAuth client *you* create, and caches a refresh token locally. The author has zero access to your data.

- **Why your own client?** Google's restricted scopes (here, the full `drive` scope) can't be redistributed in a shared app, and an unverified shared app is capped at 100 users. "Bring your own OAuth client" is the standard pattern for personal-data MCP servers.
- **What you need:** a free Google Cloud project, the Drive API enabled, an OAuth consent screen, and a Desktop OAuth client. Full walkthrough → [docs/setup-google-oauth.md](docs/setup-google-oauth.md).
- **Where your token lives:** `~/.config/google-drive-files-mcp/token.json` (mode `0600`). Delete it to revoke locally; revoke fully at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).
- **No hosted/SaaS option** — everything runs locally; your Drive data never touches a third-party server.

## More guides

- [docs/setup-google-oauth.md](docs/setup-google-oauth.md) — full OAuth walkthrough (full-`drive` scope) + common errors
- [docs/claude-code.md](docs/claude-code.md) · [docs/claude-desktop.md](docs/claude-desktop.md) · [docs/other-clients.md](docs/other-clients.md)
- [examples/](examples/) — e.g. file a document into a `YYYY-MM` folder

## Related tools

Part of a small family of focused, local MCP servers for Google Workspace data the hosted connectors don't expose:

- **[gmail-attachments-mcp](https://github.com/zayansalman/gmail-attachments-mcp)** — download Gmail attachment bytes to disk
- **[google-drive-comments-mcp](https://github.com/zayansalman/google-drive-comments-mcp)** — read comment threads on Docs/Sheets/Slides
- **google-drive-files-mcp** — move/organize Drive files *(this repo)*

They can share one OAuth login or stay isolated — see each repo's setup.

## License

MIT. See [LICENSE](LICENSE).
