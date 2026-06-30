Audit Kapa GitHub Code ingestion for required coti-io repos.

## Inputs

1. Read `kapa-required-repos.yaml` in this repository.
2. Audit every repo under `required:` (ignore `optional_legacy` and `optional_tier3` unless you have spare time).

## Verification method

For each required repo, use the **coti-knowledge** MCP (`search_coti_knowledge_sources`) with a targeted query such as:

> Is coti-io/{repo} ingested as GitHub Code with a `# Coti-io > {RepoName} > Blob` source tag?

Treat a repo as **INGESTED** only when returned chunks include a source path matching:

`# Coti-io > <RepoName> > Blob > ...`

(case-insensitive repo segment; `Blob` means GitHub Code, not docs-only crawl)

Treat as **MISSING** when no such Blob-tagged chunks appear after a focused query.

Notes:
- Kapa may normalize repo casing in tags (e.g. `Gcevm-node` for `gcEVM-node`). Match generously on repo identity.
- Empty or sparse repos may be hard to probe; if uncertain, mark as **UNCERTAIN** and mention in Slack.

## Output rules

Build three lists: INGESTED, MISSING, UNCERTAIN.

### If MISSING and UNCERTAIN are both empty

Respond with exactly:

`OK: all required repos are ingested in Kapa.`

Do **not** post to Slack.

### If MISSING or UNCERTAIN is non-empty

Post **one** Slack message with:

- **Title:** `Kapa ingestion gap — N repo(s) need attention`
- **MISSING** repos as bullets with `priority` from the YAML
- **UNCERTAIN** repos (if any) under a separate subheading
- **Fix:** Add each missing repo in Kapa → Sources → GitHub Code (one source per repo). Refreshes are automatic (~hourly) after add.
- **Link:** https://docs.kapa.ai/data-sources/github-code

Keep the message concise and actionable.

## Constraints

- Do **not** attempt to add or refresh Kapa sources — there is no public API for that.
- Do **not** post to Slack when everything required is ingested.
