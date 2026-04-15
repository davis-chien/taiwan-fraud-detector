"""
Convert raw scraped data into knowledge base markdown files using Claude.

Reads raw dumps from scrapers/raw/*/
Writes KB markdown files to knowledge_base/

Claude extracts the structured fraud pattern from each article/post.
A human should review the generated files before committing.

Usage:
    python scrapers/build_kb.py                    # process all sources
    python scrapers/build_kb.py --source twcert    # one source only
    python scrapers/build_kb.py --dry-run          # preview without writing
"""

import argparse
import json
import time
from pathlib import Path

import anthropic

RAW_DIR = Path(__file__).parent / "raw"
KB_DIR = Path(__file__).parent.parent / "knowledge_base"
KB_DIR.mkdir(exist_ok=True)

EXTRACTION_SYSTEM_PROMPT = """\
You are a fraud pattern analyst specializing in Taiwan cybercrime and online scams.

You will receive raw text from a scraped article or community post about fraud in Taiwan.
Your job is to extract the fraud pattern and format it as a structured knowledge base document.

Output ONLY the markdown document below, with no extra text before or after.
If the content does not describe a specific fraud pattern (e.g. it is a general statistics
report, an unrelated tech article, or too vague to be useful), output exactly: SKIP

---

Use this exact format:

# Pattern ID: {snake_case_id}
## Name: {English name} ({Chinese name})
## Category: {category}
## Risk level: {high|medium|low}
## Description
{2–3 sentences describing how this scam works}
## Red flag signals
- {signal 1}
- {signal 2}
- {add more as needed}
## Example message wording (話術)
{Paste the actual fraud message text if quoted in the source, or write a representative example in zh-TW based on the described pattern. This is the most important field — make it realistic.}
## Keywords (zh-TW)
{comma-separated keywords that would appear in this type of fraud message or on the fraudulent page}
## Common URLs / domains
{known fraudulent domains or URL patterns, or "(none)" if not applicable}
## Source
{source name and date}

---

Category must be exactly one of:
- fake_bank_login
- line_messaging_scam
- investment_scam
- fake_delivery
- installment_cancellation
- romance_scam
- lottery_prize_scam
- government_impersonation
- other

Pattern ID rules:
- Prefix with tw_
- Use the category as a guide (e.g. tw_fake_bank_login, tw_investment_scam_2)
- If multiple patterns of the same category exist, append _2, _3, etc.
- Keep it lowercase with underscores only

Risk level guide:
- high: leads to immediate financial loss or credential theft with one click
- medium: requires further social engineering steps before loss
- low: awareness/informational, unlikely to cause direct loss
"""


def extract_pattern(
    content: str,
    source: str,
    date: str,
    client: anthropic.Anthropic,
) -> str | None:
    """Ask Claude to extract a fraud pattern from raw content. Returns None to skip."""
    # Truncate long content — 4000 chars is enough for pattern extraction
    truncated = content[:4000]
    if len(content) > 4000:
        truncated += "\n\n[content truncated]"

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Source: {source}\n"
                    f"Date: {date}\n\n"
                    f"Content:\n{truncated}"
                ),
            }
        ],
    )

    result = message.content[0].text.strip()
    if result.upper() == "SKIP":
        return None
    return result


def parse_pattern_id(markdown: str) -> str:
    """Extract the pattern ID from the first line of the markdown."""
    first_line = markdown.split("\n")[0]
    pattern_id = first_line.replace("# Pattern ID:", "").strip()
    # Sanitize: keep only alphanumeric and underscores
    pattern_id = "".join(c if c.isalnum() or c == "_" else "_" for c in pattern_id)
    return pattern_id or "tw_unknown"


def unique_kb_path(pattern_id: str) -> Path:
    """Return a path that doesn't overwrite an existing file."""
    base = KB_DIR / f"{pattern_id}.md"
    if not base.exists():
        return base
    for suffix in range(2, 100):
        candidate = KB_DIR / f"{pattern_id}_{suffix}.md"
        if not candidate.exists():
            return candidate
    return KB_DIR / f"{pattern_id}_new.md"


def process_source(
    source_name: str,
    records: list[dict],
    client: anthropic.Anthropic,
    dry_run: bool,
) -> tuple[int, int]:
    """Process a list of raw records. Returns (saved, skipped) counts."""
    saved = skipped = 0

    for i, record in enumerate(records):
        title = record.get("title", "")[:70]
        content = record.get("content", "")
        date = record.get("date", "unknown")

        if not content.strip():
            print(f"  [{i+1}/{len(records)}] SKIP (empty content): {title}")
            skipped += 1
            continue

        print(f"  [{i+1}/{len(records)}] {title}")

        pattern = extract_pattern(content, source_name, date, client)

        if pattern is None:
            print("    → SKIP (Claude: not a specific fraud pattern)")
            skipped += 1
        else:
            pattern_id = parse_pattern_id(pattern)
            out_path = unique_kb_path(pattern_id)

            if dry_run:
                print(f"    → DRY RUN: would write {out_path.name}")
                print("    " + pattern[:200].replace("\n", "\n    ") + "...")
            else:
                out_path.write_text(pattern, encoding="utf-8")
                print(f"    → saved {out_path.name}")
            saved += 1

        # Polite rate limit — Claude API
        time.sleep(0.5)

    return saved, skipped


def load_raw(source: str) -> list[dict]:
    """Load raw records for a given source name."""
    paths = {
        "twcert": RAW_DIR / "twcert" / "articles.json",
        "ptt": RAW_DIR / "ptt" / "posts.json",
        "news": RAW_DIR / "news" / "articles.json",
    }
    path = paths.get(source)
    if not path or not path.exists():
        print(f"[{source}] No raw data found at {path}. Run the scraper first.")
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    print(f"[{source}] Loaded {len(records)} records from {path}")
    return records


def main(sources: list[str], dry_run: bool) -> None:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    total_saved = total_skipped = 0

    for source in sources:
        records = load_raw(source)
        if not records:
            continue

        source_label = {
            "twcert": "TWCERT/CC",
            "ptt": "PTT Gossiping",
            "news": "Taiwan News (CNA/UDN)",
        }.get(source, source)

        print(f"\n{'='*60}")
        print(f"Processing {source_label} ({len(records)} records)")
        print("=" * 60)

        saved, skipped = process_source(source_label, records, client, dry_run)
        total_saved += saved
        total_skipped += skipped

    print(f"\n{'='*60}")
    print(f"Done. Saved: {total_saved} | Skipped: {total_skipped}")
    if not dry_run:
        print(f"\nKB files written to: {KB_DIR}")
        print("Review the files and edit as needed before committing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate KB markdown files from raw scrapes using Claude"
    )
    parser.add_argument(
        "--source",
        choices=["twcert", "ptt", "news", "all"],
        default="all",
        help="Which raw source to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview extractions without writing any files",
    )
    args = parser.parse_args()

    sources = ["twcert", "ptt", "news"] if args.source == "all" else [args.source]
    main(sources=sources, dry_run=args.dry_run)
