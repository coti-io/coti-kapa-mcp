#!/usr/bin/env python3
"""Compare kapa-required-repos.yaml against Kapa configured sources + retrieval probes."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "kapa-required-repos.yaml"
KAPA_API = "https://api.kapa.ai"
BLOB_TAG = re.compile(r"#\s*coti-io\s*>\s*([^>]+?)\s*>\s*blob\s*>", re.I)
REPO_SLUG = re.compile(r"(?:github\.com/|repos/)([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", re.I)
ORG_REPO = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")

REPO_KEYS = frozenset(
    {
        "repository",
        "repo",
        "repo_name",
        "repository_name",
        "github_repo",
        "github_repository",
        "name",
    }
)
GITHUB_TYPE_MARKERS = ("github", "git_hub")


def load_required_repos(path: Path) -> tuple[str, list[dict]]:
    text = path.read_text(encoding="utf-8")
    org = "coti-io"
    for line in text.splitlines():
        m = re.match(r"^org:\s*(\S+)\s*$", line)
        if m:
            org = m.group(1)
            break

    repos: list[dict] = []
    section = None
    for line in text.splitlines():
        if re.match(r"^required:\s*$", line):
            section = "required"
            continue
        if section != "required":
            continue
        m = re.match(r"^\s*-\s*repo:\s*(\S+)\s*$", line)
        if m:
            repos.append({"repo": m.group(1), "priority": "unknown"})
            continue
        m = re.match(r"^\s*priority:\s*(\S+)\s*$", line)
        if m and repos:
            repos[-1]["priority"] = m.group(1)
            continue
        if re.match(r"^\S", line) and not line.startswith("#"):
            section = None

    if not repos:
        raise SystemExit(f"No required repos parsed from {path}")
    return org, repos


def http_json(method: str, url: str, api_key: str, payload: dict | None = None) -> object:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Kapa API {exc.code} for {url}: {detail}") from exc


def normalize_repo(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def add_repo_slug(store: set[str], owner: str | None, repo: str | None) -> None:
    if not repo:
        return
    store.add(normalize_repo(repo))
    if owner:
        store.add(normalize_repo(f"{owner}/{repo}"))


def walk_for_repos(node: object, org: str, found: set[str]) -> None:
    if isinstance(node, dict):
        owner = None
        for key in ("owner", "github_owner", "organization", "org"):
            val = node.get(key)
            if isinstance(val, str) and val.strip():
                owner = val.strip()
                break
        if not owner:
            owner = org

        source_type = " ".join(
            str(node.get(k, "")) for k in ("source_type", "type", "kind", "integration")
        ).lower()

        for key, val in node.items():
            if key in REPO_KEYS and isinstance(val, str) and val.strip():
                if "github" in source_type or key != "name" or "/" in val:
                    if ORG_REPO.match(val.strip()):
                        o, r = val.strip().split("/", 1)
                        add_repo_slug(found, o, r)
                    else:
                        add_repo_slug(found, owner, val.strip())
            elif isinstance(val, str):
                m = REPO_SLUG.search(val)
                if m:
                    add_repo_slug(found, m.group(1), m.group(2))
                for tag in BLOB_TAG.findall(val):
                    add_repo_slug(found, org, tag.strip())
            walk_for_repos(val, org, found)
    elif isinstance(node, list):
        for item in node:
            walk_for_repos(item, org, found)
    elif isinstance(node, str):
        m = REPO_SLUG.search(node)
        if m:
            add_repo_slug(found, m.group(1), m.group(2))


def list_sources(project_id: str, api_key: str) -> object:
    url = f"{KAPA_API}/ingestion/v1/projects/{project_id}/sources/"
    return http_json("GET", url, api_key)


def retrieval_has_blob(project_id: str, api_key: str, org: str, repo: str) -> bool:
    query = (
        f"Is {org}/{repo} ingested as GitHub Code with "
        f"# Coti-io > {repo} > Blob source tag?"
    )
    url = f"{KAPA_API}/query/v1/projects/{project_id}/retrieval/"
    data = http_json("POST", url, api_key, {"query": query})

    chunks: list[str] = []

    def collect_strings(node: object) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("source_url", "url", "title", "source", "path") and isinstance(v, str):
                    chunks.append(v)
                if k in ("content", "text", "markdown") and isinstance(v, str):
                    chunks.append(v)
                collect_strings(v)
        elif isinstance(node, list):
            for item in node:
                collect_strings(item)
        elif isinstance(node, str):
            chunks.append(node)

    collect_strings(data)
    target = normalize_repo(repo)
    for chunk in chunks:
        tag = BLOB_TAG.search(chunk)
        if tag and normalize_repo(tag.group(1)) == target:
            return True
        if BLOB_TAG.search(chunk) and normalize_repo(repo) in normalize_repo(chunk):
            return True
    return False


def configured_repos(sources_payload: object, org: str) -> set[str]:
    found: set[str] = set()
    walk_for_repos(sources_payload, org, found)
    return found


def is_present(repo: str, configured: set[str]) -> bool:
    slug = normalize_repo(repo)
    return slug in configured or any(slug in item or item in slug for item in configured)


def post_slack(webhook: str, text: str) -> None:
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status >= 300:
            raise SystemExit(f"Slack webhook returned {resp.status}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Kapa GitHub Code ingestion gaps.")
    parser.add_argument("--yaml", type=Path, default=YAML_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Print report; do not Slack.")
    parser.add_argument(
        "--verify-retrieval",
        action="store_true",
        help="For repos missing from sources list, probe retrieval API for Blob tags.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("KAPA_API_KEY", "").strip()
    project_id = os.environ.get("KAPA_PROJECT_ID", "").strip()
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()

    if not api_key or not project_id:
        raise SystemExit("Set KAPA_API_KEY and KAPA_PROJECT_ID environment variables.")

    org, required = load_required_repos(args.yaml)
    sources = list_sources(project_id, api_key)
    configured = configured_repos(sources, org)

    ingested: list[str] = []
    missing: list[dict] = []
    uncertain: list[dict] = []

    for entry in required:
        repo = entry["repo"]
        if is_present(repo, configured):
            ingested.append(repo)
            continue

        if args.verify_retrieval and retrieval_has_blob(project_id, api_key, org, repo):
            ingested.append(repo)
            continue

        if args.verify_retrieval:
            uncertain.append(entry)
        else:
            missing.append(entry)

    print(f"Configured GitHub-related source slugs seen: {len(configured)}")
    print(f"Required repos: {len(required)}")
    print(f"Ingested/configured: {len(ingested)}")
    print(f"Missing: {len(missing)}")
    if uncertain:
        print(f"Uncertain: {len(uncertain)}")

    if missing:
        print("\nMISSING:")
        for entry in missing:
            print(f"  - {entry['repo']} ({entry['priority']})")
    if uncertain:
        print("\nUNCERTAIN:")
        for entry in uncertain:
            print(f"  - {entry['repo']} ({entry['priority']})")

    gaps = missing + uncertain
    if not gaps:
        print("\nOK: all required repos are ingested in Kapa.")
        return 0

    lines = [
        f"*Kapa ingestion gap — {len(gaps)} repo(s) need attention*",
        "",
        "These required repos are not configured as GitHub Code sources in Kapa:",
        "",
    ]
    for entry in gaps:
        lines.append(f"• `{entry['repo']}` ({entry['priority']})")
    lines.extend(
        [
            "",
            "Fix: Kapa → Sources → GitHub Code (one source per repo).",
            "Docs: https://docs.kapa.ai/data-sources/github-code",
        ]
    )
    message = "\n".join(lines)

    if args.dry_run:
        print("\n--- Slack message (dry-run) ---")
        print(message)
        return 1

    if not webhook:
        raise SystemExit("Gaps found but SLACK_WEBHOOK_URL is not set.")

    post_slack(webhook, message)
    print("\nSlack alert sent.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
