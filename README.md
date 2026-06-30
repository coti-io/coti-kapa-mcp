# coti-kapa-mcp

Policy and automation for keeping **coti-io** GitHub repos ingested in [Kapa](https://kapa.ai) as GitHub Code sources.

Kapa has no public API to **add** sources — only to **list** them and query retrieval. This repo defines which repos must be ingested and runs a scheduled audit that **Slack-alerts on gaps**.

Repo: https://github.com/coti-io/coti-kapa-mcp

## Files

| File | Purpose |
|------|---------|
| `kapa-required-repos.yaml` | Allowlist of repos that must be in Kapa |
| `.scripts/kapa-ingestion-audit.py` | Compares allowlist vs Kapa sources API (+ optional retrieval probe) |
| `.github/workflows/kapa-ingestion-audit.yml` | Scheduled GitHub Action (weekdays) |
| `.cursor/automation/kapa-ingestion-audit.workflow.json` | Optional Cursor Automation prefill (Agents Window) |

## Setup (GitHub Action — recommended)

### 1. Add GitHub secrets

Add secrets to the **`main` environment** (Settings → Environments → **main** → Environment secrets):

| Secret | Where to get it |
|--------|-----------------|
| `KAPA_API_KEY` | Kapa project → Settings → API keys ([API FAQ](https://docs.kapa.ai/api/faq)) |
| `KAPA_PROJECT_ID` | Kapa project settings or URL (UUID) |
| `SLACK_WEBHOOK_URL` | Slack app → Incoming Webhooks → channel webhook URL |

The workflow job sets `environment: main` so these environment secrets are injected. Repository-level secrets also work if you prefer those instead.

Do **not** commit API keys or paste them in chat.

```bash
gh secret set KAPA_API_KEY --env main --repo coti-io/coti-kapa-mcp
gh secret set KAPA_PROJECT_ID --env main --repo coti-io/coti-kapa-mcp
gh secret set SLACK_WEBHOOK_URL --env main --repo coti-io/coti-kapa-mcp
```

### 2. Test locally (optional)

```bash
cp .env.example .env
# fill in .env, then:
set -a && source .env && set +a
python3 .scripts/kapa-ingestion-audit.py --dry-run --verify-retrieval
```

### 3. Run on GitHub

- **Automatic:** weekdays 07:00 UTC (see workflow cron)
- **Manual:** Actions → *Kapa ingestion audit* → *Run workflow*

## Behavior

1. Reads `kapa-required-repos.yaml` (`required:` section).
2. Calls `GET /ingestion/v1/projects/{id}/sources/` ([List sources](https://docs.kapa.ai/api/reference/ingestion-v-1-projects-sources-list)).
3. Optionally probes retrieval for `# Coti-io > <repo> > Blob` tags (`--verify-retrieval`).
4. **All good:** prints `OK: all required repos are ingested in Kapa.` — no Slack.
5. **Gaps:** posts one Slack message with repo list, priority, and [GitHub Code setup link](https://docs.kapa.ai/data-sources/github-code).

## Updating the allowlist

When a new Production repo should be searchable in Kapa:

1. Add it under `required:` in `kapa-required-repos.yaml` with a priority.
2. Commit and push.
3. Add the GitHub Code source once in the Kapa Sources UI.

The audit catches repos on the list that were never added to Kapa.

## Optional: Cursor Cloud Automation

If you prefer a Cursor Cloud Agent + MCP instead of GitHub Actions, create an automation in the **Agents Window** from:

`.cursor/automation/kapa-ingestion-audit.workflow.json`

See `.cursor/automation/kapa-ingestion-audit.prompt.md` for full agent instructions. Pick your Slack channel in the Automations editor.

## Related

- [github-projects-monitor](https://github.com/coti-io/github-projects-monitor) — repo compliance (`repo-controls-summary-coti-io.md`)
- [Kapa GitHub Code docs](https://docs.kapa.ai/data-sources/github-code)
