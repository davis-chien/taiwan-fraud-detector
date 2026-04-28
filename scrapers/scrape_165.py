"""
Scrape fraud case descriptions from 165.npa.gov.tw.

165 is Taiwan's National Police Agency anti-fraud hotline. The site publishes
real fraud case write-ups with actual message excerpts and scam 話術 (scripts),
making it the highest-quality labeled source for this project.

Source: https://165.npa.gov.tw/#/article/crime
Output: scrapers/raw/165/cases.json

Usage:
    python scrapers/scrape_165.py
    python scrapers/scrape_165.py --max-pages 10 --category investment
"""

import argparse
import json
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://165.npa.gov.tw"

# API endpoint used by the SPA for paginated case listings
API_CASES = f"{BASE_URL}/api/article/crime"
API_ARTICLE = f"{BASE_URL}/api/article"

# Category slugs exposed by the 165 API
CATEGORIES = [
    "investment",    # 假投資詐騙
    "romance",       # 假交友詐騙
    "shopping",      # 網購詐騙
    "job",           # 假求職詐騙
    "phishing",      # 網路釣魚
    "impersonation", # 冒充官員
    "lottery",       # 中獎詐騙
    "delivery",      # 假包裹
]

RAW_DIR = Path(__file__).parent / "raw" / "165"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://165.npa.gov.tw/",
}


def fetch_json(url: str, params: dict, client: httpx.Client) -> dict | None:
    try:
        resp = client.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return None


def fetch_html(url: str, client: httpx.Client) -> BeautifulSoup | None:
    try:
        resp = client.get(url, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return None


def scrape_api(category: str, client: httpx.Client, max_pages: int) -> list[dict]:
    """Collect case metadata via the 165 JSON API (SPA backend)."""
    cases = []
    page = 1

    while page <= max_pages:
        data = fetch_json(
            API_CASES,
            params={"category": category, "page": page, "size": 20},
            client=client,
        )
        if not data:
            break

        items = data.get("data") or data.get("list") or data.get("items") or []
        if not items:
            break

        for item in items:
            cases.append({
                "id": item.get("id") or item.get("articleId", ""),
                "title": item.get("title", ""),
                "date": item.get("publishDate") or item.get("date", ""),
                "category": category,
                "source_url": f"{BASE_URL}/#/article/crime/{item.get('id', '')}",
            })

        total_pages = data.get("totalPages") or data.get("pages", page)
        if page >= total_pages:
            break
        page += 1
        time.sleep(1.5)

    return cases


def scrape_html_listing(client: httpx.Client, max_pages: int) -> list[dict]:
    """
    Fallback: scrape the rendered HTML listing page when the API is unavailable
    or returns an unexpected schema.
    """
    cases = []
    url = f"{BASE_URL}/#/article/crime"

    for page in range(1, max_pages + 1):
        soup = fetch_html(f"{BASE_URL}/article/crime?page={page}", client)
        if not soup:
            break

        for item in soup.select("article, .case-item, .news-item, li.item"):
            title_el = item.select_one("h2, h3, .title, a")
            date_el = item.select_one(".date, time, .publish-date")
            link_el = item.select_one("a[href]")

            if not title_el:
                continue

            href = link_el["href"] if link_el else ""
            if href and not href.startswith("http"):
                href = BASE_URL + href

            cases.append({
                "id": "",
                "title": title_el.get_text(strip=True),
                "date": date_el.get_text(strip=True) if date_el else "",
                "category": "unknown",
                "source_url": href,
            })

        time.sleep(1.5)

    return cases


def fetch_article_content(case: dict, client: httpx.Client) -> str:
    """Fetch the full article text for a single case."""
    article_id = case.get("id")
    if article_id:
        # Try the API endpoint first
        data = fetch_json(f"{API_ARTICLE}/{article_id}", {}, client)
        if data:
            content = (
                data.get("content")
                or data.get("body")
                or data.get("description", "")
            )
            if isinstance(content, str) and content.strip():
                soup = BeautifulSoup(content, "lxml")
                return soup.get_text(separator="\n", strip=True)

    # Fallback: fetch the HTML page
    url = case.get("source_url", "")
    if not url or url.endswith("/"):
        return ""

    soup = fetch_html(url, client)
    if not soup:
        return ""

    for el in soup.select("nav, header, footer, .breadcrumb, script, style"):
        el.decompose()

    content_el = (
        soup.select_one("article")
        or soup.select_one(".content")
        or soup.select_one("main")
        or soup.select_one("body")
    )
    if not content_el:
        return ""

    return content_el.get_text(separator="\n", strip=True)


def main(categories: list[str], max_pages: int = 5) -> None:
    out_path = RAW_DIR / "cases.json"

    existing: list[dict] = []
    existing_ids: set[str] = set()
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        existing_ids = {c.get("id", c.get("source_url", "")) for c in existing}
        print(f"Resuming — {len(existing)} cases already scraped.")

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        all_cases: list[dict] = []
        seen: set[str] = set()

        for cat in categories:
            print(f"Collecting category: {cat}")
            cases = scrape_api(cat, client, max_pages)

            if not cases:
                print(f"  API returned nothing for '{cat}', trying HTML fallback...")
                cases = scrape_html_listing(client, max_pages)

            new = [c for c in cases if c.get("id", c.get("source_url")) not in seen]
            seen.update(c.get("id", c.get("source_url")) for c in new)
            all_cases.extend(new)
            print(f"  → {len(cases)} results, {len(new)} unique new | total: {len(all_cases)}")
            time.sleep(2)

        to_fetch = [
            c for c in all_cases
            if c.get("id", c.get("source_url", "")) not in existing_ids
        ]
        print(f"\nFetching article content for {len(to_fetch)} new cases...")

        results = list(existing)
        for i, case in enumerate(to_fetch):
            print(f"[{i+1}/{len(to_fetch)}] {case['title'][:70]}")
            content = fetch_article_content(case, client)
            if content:
                results.append({**case, "content": content})
                print(f"  → OK ({len(content)} chars)")
            else:
                print("  → skipped (no content)")
            time.sleep(1.5)

        out_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nSaved {len(results)} total cases to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape fraud cases from 165.npa.gov.tw")
    parser.add_argument(
        "--categories",
        nargs="+",
        default=CATEGORIES,
        help="Category slugs to scrape",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Max listing pages per category",
    )
    args = parser.parse_args()
    main(categories=args.categories, max_pages=args.max_pages)
