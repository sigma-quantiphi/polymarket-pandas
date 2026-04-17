"""Triage new Polymarket changelog entries and open GitHub issues per verdict.

Fetches https://docs.polymarket.com/changelog/rss.xml, diffs against a committed
seen-list (`.github/changelog-seen.json`), and for each new entry asks Claude
whether the change requires updates in polymarket-pandas. Verdicts are posted
as labeled GitHub issues via the `gh` CLI.

Env vars:
    ANTHROPIC_API_KEY   required
    GH_TOKEN            required (GH runner provides this; local: use `gh auth token`)
    DRY_RUN             if truthy, print verdicts but skip issue creation and state writes
    FORCE_GUID          if set, triage this GUID even if it's already in the seen-list

First-run behavior: if the seen-list doesn't exist, seed it with every current
GUID and open no issues. Only genuinely new entries on subsequent runs are triaged.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import anthropic
import feedparser

RSS_URL = "https://docs.polymarket.com/changelog/rss.xml"
STATE_PATH = Path(__file__).resolve().parent.parent / ".github" / "changelog-seen.json"
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 2048

MIXINS = [
    "_gamma",
    "_data",
    "_clob_public",
    "_clob_private",
    "_rewards",
    "_relayer",
    "_bridge",
    "_ctf",
    "_uma",
    "_xtracker",
]
CATEGORIES = [
    "new_endpoint",
    "endpoint_change",
    "schema_change",
    "auth_change",
    "deprecation",
    "docs_only",
    "unrelated",
]

LABELS = [
    ("changelog", "0E8A16", "Polymarket changelog entry surfaced by automation"),
    ("needs-integration", "D93F0B", "Requires a code change in polymarket-pandas"),
    ("info-only", "CCCCCC", "No code change required"),
]


ARCH_CONTEXT = textwrap.dedent(
    """\
    polymarket-pandas is a pandas-native Python client for the full Polymarket API.
    Your job is to triage Polymarket changelog entries and decide whether each one
    requires a code change in this library.

    ## Package layout

    The sync client `PolymarketPandas` is a dataclass composing 9 mixins. Each mixin
    owns a slice of the API surface. The async client `AsyncPolymarketPandas` wraps
    sync methods via a ThreadPoolExecutor and does NOT own any endpoint logic —
    changes to the sync mixins propagate automatically.

    - `_gamma` — Gamma API (`https://gamma-api.polymarket.com/`).
      Discovery endpoints: markets, events, series, tags, comments, search, profiles,
      sports metadata, teams. Both offset pagination (`get_markets`, `get_events`)
      and keyset pagination (`get_markets_keyset`, `get_events_keyset`).
    - `_data` — Data API (`https://data-api.polymarket.com/`).
      Portfolio + analytics: positions, closed positions, market positions, top holders,
      trades, leaderboard, builder leaderboard, builder volume, position value,
      user activity, live volume, open interest, traded markets count.
    - `_clob_public` — Public CLOB endpoints. Orderbook, orderbooks, price, midpoint,
      spread, last trade price, price history, sampling/simplified markets,
      tick size, neg risk, fee rate.
    - `_clob_private` — Authenticated CLOB endpoints (L2 HMAC). User trades,
      active/historic orders, place order, cancel orders, create/derive API key,
      heartbeat, balance & allowance.
    - `_rewards` — Rewards API. Current rewards, rewards-by-market, user earnings,
      user reward markets, rebates.
    - `_relayer` — Relayer API (`relayer-v2`). Safe deployment, nonces, transactions,
      relay payload, submit transaction.
    - `_bridge` — Bridge API. Supported assets, deposit/withdrawal address, quote,
      transaction status.
    - `_ctf` — On-chain Conditional Token Framework ops (requires `[ctf]` extra,
      depends on web3). Split, merge, redeem, batch ops, approve collateral,
      gas estimation. Proxy-wallet aware (GSN-relayed via builder HMAC).
    - `_uma` — UMA CTF Adapter + OptimisticOracleV2 on Polygon. Propose/dispute
      prices, settle OO, resolve market, read question state. Shares `[ctf]` extra.
    - `_xtracker` — xtracker.polymarket.com post-counter API (X / Truth Social
      tracking feeds).

    ## Entity hierarchy + ID systems

    Polymarket entities form Series -> Events -> Markets -> Tokens.
    Two parallel ID spaces:
    - Gamma uses slugs + numeric IDs + nested JSON.
    - CLOB / Data APIs use `conditionId` (one per market) + `clobTokenIds` (one
      per outcome). The `market` parameter means token ID in the Data API but
      condition ID in CLOB private.

    ## DataFrame conventions

    Every list-returning method returns a `DataFrame[Schema]` validated by a
    pandera schema in `schemas.py`. Every dict-returning method returns a
    `TypedDict` from `types.py`. `preprocess_dataframe` coerces types by column
    name: numeric columns to float, ISO/Unix-ms datetime columns to pd.Timestamp,
    bool columns to bool, JSON-string columns parsed into Python objects.
    snake_case keys are camelCased.

    Nested fields (`events`, `eventsSeries`, `markets`) are expanded inline via
    `expand_dataframe` when flags like `expand_events=True` are set. Cursor-paginated
    endpoints return `CursorPage` TypedDicts. Keyset endpoints return
    `MarketsKeysetPage` / `EventsKeysetPage`.

    ## Auth layers

    - L1 (EIP-712): only for `create_api_key` / `derive_api_key`. Needs `private_key`.
    - L2 (HMAC-SHA256): all private CLOB endpoints.
    - Builder HMAC: for `get_builder_trades`, and auto-attached as attribution on
      `place_order`/`place_orders` when builder creds are present.
    - Relayer key: plain headers RELAYER_API_KEY + RELAYER_API_KEY_ADDRESS.

    ## What counts as "requires integration"

    - New HTTP endpoint not already covered by any mixin -> add a method there.
    - New query parameter, request field, or response field on an existing
      endpoint -> update signature + pandera schema + TypedDict.
    - Renamed/removed field -> update schema + add a migration note.
    - Authentication change -> update `_build_*_headers` and the auth guards.
    - New rate limits, base URLs, or pagination shape -> update `_request_*`
      helpers or pagination utilities.
    - New on-chain contract address or ABI -> update `_ctf.py` or `_uma.py`.

    ## What does NOT require integration

    - UI/dashboard-only changes on polymarket.com itself.
    - Marketing announcements, new features that don't touch the public API.
    - Docs wording edits with no underlying endpoint change.
    - Purely backend/internal changes that aren't exposed on the public API surface.

    When in doubt, mark `requires_integration=true` and explain what needs
    investigation. False positives are cheap (human reads the issue and closes);
    false negatives are expensive (we silently miss an API change).
    """
)


TOOL = {
    "name": "record_verdict",
    "description": (
        "Record a triage verdict for a Polymarket changelog entry. "
        "Call this exactly once per entry."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "requires_integration": {
                "type": "boolean",
                "description": (
                    "True if the entry likely requires a code change in "
                    "polymarket-pandas. Prefer true when uncertain."
                ),
            },
            "category": {
                "type": "string",
                "enum": CATEGORIES,
                "description": "Best-fit category for the change.",
            },
            "affected_mixin": {
                "type": "string",
                "enum": [*MIXINS, ""],
                "description": (
                    "Which mixin file is most likely to change. Empty string if "
                    "not applicable (docs-only, unrelated, unclear)."
                ),
            },
            "affected_methods": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Existing method names that likely need updates, OR the "
                    "literal 'NEW' if this is a net-new endpoint. Empty array "
                    "if no specific methods map."
                ),
            },
            "summary": {
                "type": "string",
                "description": "One-sentence plain-English summary of the change.",
            },
            "suggested_change": {
                "type": "string",
                "description": (
                    "One short paragraph describing what to implement: which "
                    "method to add/update, which schema + TypedDict to touch, "
                    "which mixin file, and what tests to add. Be specific."
                ),
            },
        },
        "required": [
            "requires_integration",
            "category",
            "affected_mixin",
            "affected_methods",
            "summary",
            "suggested_change",
        ],
    },
}


@dataclass
class Entry:
    guid: str
    title: str
    link: str
    pub_date: str
    html: str


@dataclass
class Verdict:
    requires_integration: bool
    category: str
    affected_mixin: str
    affected_methods: list[str]
    summary: str
    suggested_change: str


def load_seen() -> list[str] | None:
    """Return the sorted list of seen GUIDs, or None if the state file is missing."""
    if not STATE_PATH.exists():
        return None
    with STATE_PATH.open() as f:
        return json.load(f)


def write_seen(guids: list[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w") as f:
        json.dump(sorted(guids), f, indent=2)
        f.write("\n")


def fetch_entries() -> list[Entry]:
    feed = feedparser.parse(RSS_URL)
    if feed.bozo:
        raise RuntimeError(f"RSS parse error: {feed.bozo_exception}")
    out = []
    for e in feed.entries:
        guid = getattr(e, "id", None) or getattr(e, "guid", None) or e.link
        html = ""
        if hasattr(e, "content") and e.content:
            html = e.content[0].get("value", "")
        elif hasattr(e, "summary"):
            html = e.summary
        out.append(
            Entry(
                guid=guid,
                title=e.title,
                link=e.link,
                pub_date=getattr(e, "published", ""),
                html=html,
            )
        )
    return out


def triage(client: anthropic.Anthropic, entry: Entry) -> Verdict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": ARCH_CONTEXT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "record_verdict"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Changelog entry title: {entry.title}\n"
                    f"Published: {entry.pub_date}\n"
                    f"Link: {entry.link}\n\n"
                    f"HTML content:\n{entry.html}"
                ),
            }
        ],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_verdict":
            data = block.input
            return Verdict(
                requires_integration=bool(data["requires_integration"]),
                category=data["category"],
                affected_mixin=data["affected_mixin"],
                affected_methods=list(data["affected_methods"]),
                summary=data["summary"],
                suggested_change=data["suggested_change"],
            )
    raise RuntimeError(
        f"Claude did not call record_verdict for {entry.guid}. stop_reason={response.stop_reason}"
    )


def gh(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args],
        check=check,
        text=True,
        capture_output=capture,
    )


def ensure_labels() -> None:
    existing = gh("label", "list", "--json", "name", "-L", "200", capture=True)
    names = {item["name"] for item in json.loads(existing.stdout or "[]")}
    for name, color, description in LABELS:
        if name in names:
            continue
        gh(
            "label",
            "create",
            name,
            "--color",
            color,
            "--description",
            description,
            check=False,
        )
    # per-category labels
    for cat in CATEGORIES:
        lname = f"cat:{cat.replace('_', '-')}"
        if lname in names:
            continue
        gh("label", "create", lname, "--color", "BFD4F2", check=False)


def render_issue_body(entry: Entry, verdict: Verdict) -> str:
    affected = verdict.affected_mixin or "(none)"
    methods = ", ".join(verdict.affected_methods) if verdict.affected_methods else "(none)"
    return (
        f"**Source**: {entry.link}\n"
        f"**Published**: {entry.pub_date}\n"
        f"**Verdict**: requires_integration={verdict.requires_integration} · "
        f"category={verdict.category}\n"
        f"**Affected**: {affected} · {methods}\n\n"
        f"### Summary\n{verdict.summary}\n\n"
        f"### Suggested change\n{verdict.suggested_change}\n\n"
        f"---\n<details><summary>Raw entry</summary>\n\n"
        f"{entry.html}\n</details>\n"
    )


def create_issue(entry: Entry, verdict: Verdict) -> str:
    labels = ["changelog"]
    labels.append("needs-integration" if verdict.requires_integration else "info-only")
    labels.append(f"cat:{verdict.category.replace('_', '-')}")
    title = f"[changelog] {entry.title}"
    result = gh(
        "issue",
        "create",
        "--title",
        title,
        "--body",
        render_issue_body(entry, verdict),
        "--label",
        ",".join(labels),
        capture=True,
    )
    return result.stdout.strip()


def main() -> int:
    dry_run = bool(os.getenv("DRY_RUN"))
    force_guid = os.getenv("FORCE_GUID") or ""

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    entries = fetch_entries()
    if not entries:
        print("Feed is empty; nothing to do.")
        return 0
    feed_guids = [e.guid for e in entries]

    seen = load_seen()
    if seen is None:
        print(f"No state file at {STATE_PATH}. Seeding {len(feed_guids)} GUIDs.")
        if not dry_run:
            write_seen(feed_guids)
        return 0

    seen_set = set(seen)
    # Process oldest-first so the issue list reads chronologically.
    new_entries = [e for e in reversed(entries) if e.guid not in seen_set]
    if force_guid:
        # Force wins even if already seen.
        extras = [e for e in reversed(entries) if e.guid == force_guid]
        if not extras:
            print(f"FORCE_GUID={force_guid!r} not found in feed.")
            return 1
        new_entries = extras

    if not new_entries:
        print("No new changelog entries.")
        return 0

    print(f"Processing {len(new_entries)} entries (dry_run={dry_run}).")
    client = anthropic.Anthropic()

    if not dry_run:
        ensure_labels()

    processed: list[str] = []
    for entry in new_entries:
        print(f"\n--- {entry.title} ({entry.guid}) ---")
        try:
            verdict = triage(client, entry)
        except anthropic.APIError as exc:
            print(f"Claude API error for {entry.guid}: {exc}", file=sys.stderr)
            # Don't mark as seen — retry next run.
            continue

        print(
            f"verdict: requires_integration={verdict.requires_integration} "
            f"category={verdict.category} affected_mixin={verdict.affected_mixin or '(none)'}"
        )
        print(f"summary: {verdict.summary}")

        if dry_run:
            processed.append(entry.guid)
            continue

        try:
            url = create_issue(entry, verdict)
            print(f"created issue: {url}")
        except subprocess.CalledProcessError as exc:
            print(f"gh issue create failed for {entry.guid}: {exc}", file=sys.stderr)
            # Don't mark as seen — retry next run.
            continue
        processed.append(entry.guid)

    if not dry_run and processed and not force_guid:
        seen_set.update(processed)
        write_seen(sorted(seen_set))
        print(f"\nUpdated state with {len(processed)} new GUIDs.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
