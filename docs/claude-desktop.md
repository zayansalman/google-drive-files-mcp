# Claude Desktop integration

After installing and running `google-drive-files-mcp setup`, edit Claude Desktop's MCP config:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "google-drive-files": {
      "command": "google-drive-files-mcp",
      "args": ["serve"]
    }
  }
}
```

If the command isn't on Claude Desktop's `$PATH`, use the absolute path from `which google-drive-files-mcp`.

## Newer Claude Desktop / Cowork builds
Some builds read MCP config from the unified `~/.claude.json` (shared with Claude Code) rather than `claude_desktop_config.json`. If editing the JSON has no effect after a restart, register via the CLI and relaunch:

```bash
claude mcp add --scope user google-drive-files google-drive-files-mcp -- serve
```

## Verify
> Create a folder called "Archive 2026" and move my oldest "Draft" doc into it.
