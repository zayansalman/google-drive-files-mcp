# Other MCP clients

Any stdio-transport MCP client can use `google-drive-files-mcp`:

- **Transport**: stdio
- **Command**: `google-drive-files-mcp` (or the absolute path)
- **Args**: `["serve"]`
- **Env** (optional): `GDRIVE_FILES_MCP_CREDENTIALS`, `GDRIVE_FILES_MCP_TOKEN`, `GDRIVE_FILES_MCP_SCOPES`

## Cursor — `~/.cursor/mcp.json`
```json
{
  "mcpServers": {
    "google-drive-files": { "command": "google-drive-files-mcp", "args": ["serve"] }
  }
}
```

## Cline (VS Code)
MCP settings → **Add MCP server** → stdio. Command `google-drive-files-mcp`, args `serve`.

## Continue.dev — `~/.continue/config.yaml`
```yaml
mcpServers:
  - name: google-drive-files
    command: google-drive-files-mcp
    args:
      - serve
```

## One-time auth per machine
Once `google-drive-files-mcp setup` has cached a token at `~/.config/google-drive-files-mcp/token.json`, every client on that machine/user reuses it — no per-client re-authentication.
