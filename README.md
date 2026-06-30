# coti-kapa-mcp

Policy and automation config for keeping **coti-io** GitHub repos ingested in [Kapa](https://kapa.ai) as GitHub Code sources.

Kapa has no public API to add sources — only to query them. This repo defines **which repos must be ingested** and ships a **Cursor Automation** that audits ingestion and Slack-alerts on gaps.

## Files

| File | Purpose |
|------|---------|
| `kapa-required-repos.yaml` | Allowlist of repos that must appear as `# Coti-io > … > Blob` in coti-knowledge |
| `.cursor/automation/kapa-ingestion-audit.workflow.json` | Cursor Automation prefill (cron + cloud agent + MCP + Slack) |
| `.cursor/automation/kapa-ingestion-audit.prompt.md` | Full agent instructions (reference copy) |

## One-time setup

### 1. Push this repo to GitHub

The Cloud Agent needs a remote checkout. Update `gitConfig.repo` in the workflow JSON if your org/repo name differs.

```bash
git init
git add .
git commit -m "Add Kapa ingestion audit config and automation prefill"
git remote add origin git@github.com:coti-io/coti-kapa-mcp.git
git push -u origin main
```

### 2. Enable Cloud Agents

[Cloud Agent dashboard](https://cursor.com/dashboard?tab=cloud-agents) — ensure cloud compute is enabled for your team.

### 3. Connect integrations

In Cursor Settings → Integrations:

- **Slack** — for alert posts
- **coti-knowledge MCP** — same server you use locally (`serverName`: `coti-knowledge`)

### 4. Create the Cursor Automation

In the **Agents Window**, ask Cursor to open the automation draft from:

`.cursor/automation/kapa-ingestion-audit.workflow.json`

Or create manually:

| Setting | Value |
|---------|-------|
| **Trigger** | Cron — weekdays 9:00 (`0 9 * * 1-5`) |
| **Repo** | This repo (`coti-io/coti-kapa-mcp`, branch `main`) |
| **Tools** | MCP: `coti-knowledge`, Post to Slack |
| **Slack channel** | Pick your alerts channel in the editor |
| **Prompt** | See `.cursor/automation/kapa-ingestion-audit.prompt.md` |

Save and enable the automation.

## Behavior

- Runs **weekdays at 9:00** (cron UTC in editor — adjust if needed).
- Reads `kapa-required-repos.yaml`.
- Probes each required repo via **coti-knowledge** for GitHub Code (`Blob`) tags.
- **Silent on success** — no Slack message when all required repos are ingested.
- **Slack alert on gaps** — lists missing repos with priority and Kapa UI fix steps.

## Updating the allowlist

When a new **Production** repo should be searchable in Kapa:

1. Add it under `required:` in `kapa-required-repos.yaml` with a priority.
2. Commit and push.
3. Add the GitHub Code source once in the [Kapa Sources UI](https://docs.kapa.ai/data-sources/github-code).

The automation will catch any repo on the list that was never added to Kapa.

## Related

- Repo compliance scanning: [github-projects-monitor](https://github.com/coti-io/github-projects-monitor) (`repo-controls-summary-coti-io.md`)
- Kapa GitHub Code docs: https://docs.kapa.ai/data-sources/github-code
