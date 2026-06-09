# Claude Code integration

After `pip install google-drive-files-mcp` and `google-drive-files-mcp setup`:

```bash
claude mcp add --scope user google-drive-files google-drive-files-mcp -- serve
```

Verify:
```bash
claude mcp list | grep google-drive-files
# google-drive-files: google-drive-files-mcp serve - ✓ Connected
```

In a session:
> Find my "Q2 Report" doc and move it into the "2026 Reports" folder.

Because this tool can move/relocate files, prefer to let it **search first and show you the matches** before moving — `drive_move` returns the before/after parents so every move is auditable.

## Remove
```bash
claude mcp remove google-drive-files
```
