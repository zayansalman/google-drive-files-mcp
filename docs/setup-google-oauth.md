# Google OAuth setup (~10 minutes)

This server **moves and organizes files in your Drive**, so it needs the **full `drive` scope** (read + write + delete on all your Drive files). There is no narrower scope that can change a file's parents. Treat the cached token like a password.

You create your own OAuth client; nothing is shipped with the package, and nothing leaves your machine.

## Step 1 — Project
1. [Google Cloud Console](https://console.cloud.google.com/) → sign in → project dropdown → **New Project** → name it → **Create** → switch to it.

## Step 2 — Enable the Drive API
[console.cloud.google.com/apis/library/drive.googleapis.com](https://console.cloud.google.com/apis/library/drive.googleapis.com) → **Enable**.

## Step 3 — OAuth consent screen
Left nav → **APIs & Services** → **OAuth consent screen**.

| You have | Pick | Why |
|---|---|---|
| Google Workspace | **Internal** | No verification needed *even for the restricted full-`drive` scope* |
| Personal Gmail | **External** | Add your address under **Test users** or consent is refused |

Fill App name / support email / developer contact. Leave the Scopes page empty. Save.

## Step 4 — OAuth client
**Credentials → + Create Credentials → OAuth client ID → Desktop app → Create → Download JSON.**

## Step 5 — Hand it to the CLI
```bash
google-drive-files-mcp setup --import-credentials ~/Downloads/client_secret_*.json
```
A browser opens; the consent screen will say **"See, edit, create, and delete all of your Google Drive files"** — that breadth is required to move arbitrary files. The refresh token is cached at `~/.config/google-drive-files-mcp/token.json` (mode `0600`).

Verify:
```bash
google-drive-files-mcp status
google-drive-files-mcp search "Reports" --folders
```

## Common errors

**`HttpError 403: Google Drive API has not been used in project … or it is disabled`**
Enable the Drive API (Step 2) on the project that owns your OAuth client, then wait ~1 min and retry.

**`Access blocked: This app's request is invalid`**
Personal Gmail without your address under **Test users**. Add it on the consent screen.

**`This app isn't verified`**
Expected for an unverified personal app. **Advanced → Go to <app> (unsafe)**. Verification only matters for public distribution.

**`HttpError 403: insufficientFilePermissions` / `insufficientPermissions` when moving**
The token was authorized with a narrower scope. Re-authorize with the full scope:
```bash
google-drive-files-mcp setup --reauth
```

**Browser opened but never returned**
Firewall blocking the localhost redirect. Re-run `setup` (new port each time) or allow the connection.
