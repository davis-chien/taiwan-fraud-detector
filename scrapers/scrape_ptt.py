"""
Scrape PTT Gossiping board for fraud-related posts.

PTT is Taiwan's largest BBS. Gossiping board users frequently share
real fraud messages they received, making it a rich source of authentic
fraud 話術 (scripts) and patterns.

Source: https://www.ptt.cc/bbs/Gossiping/search?q=<keyword>
Output: scrapers/raw/ptt/posts.json

Usage:
    python scrapers/scrape_ptt.py
    python scrapers/scrape_ptt.py --max-pages 3 --queries 詐騙 假冒銀行
"""

import argparse
import json
import time
import warnings
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# Suppress SSL warnings — PTT sometimes has certificate issues
warnings.filterwarnings("ignore", category=httpx._exceptions.ConnectError.__class__)

BASE_URL = "https://www.ptt.cc"

# Search queries to run against Gossiping board
DEFAULT_QUERIES = [
    "詐騙",
    "詐欺",
    "假冒LINE",
    "假冒銀行",
    "假包裹",
    "假投資",
    "釣魚網站",
    "假冒警察",
    "假冒健保",
    "解除分期",
]

RAW_DIR = Path(__file__).parent / "raw" / "ptt"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# PTT Gossiping board requires age-gate cookie
COOKIES = {"over18": "1"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.ptt.cc/",
}


def fetch(url: str, client: httpx.Client) -> BeautifulSoup | None:
    try:
        resp = client.get(url, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except httpx.HTTPStatusError as e:
        print(f"  [WARN] HTTP {e.response.status_code} for {url}")
        return None
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return None


def scrape_search_results(
    query: str, client: httpx.Client, max_pages: int
) -> list[dict]:
    """Search PTT Gossiping for a keyword and collect post metadata."""
    posts = []
    url = f"{BASE_URL}/bbs/Gossiping/search?q={query}"

    for _ in range(max_pages):
        soup = fetch(url, client)
        if not soup:
            break

        for item in soup.select(".r-ent"):
            title_el = item.select_one(".title a")
            date_el = item.select_one(".date")
            author_el = item.select_one(".author")

            if not title_el:
                # Deleted post
                continue

            post_url = BASE_URL + title_el["href"]
            posts.append({
                "title": title_el.get_text(strip=True),
                "url": post_url,
                "date": date_el.get_text(strip=True) if date_el else "",
                "author": author_el.get_text(strip=True) if author_el else "",
                "query": query,
            })

        # Navigate to previous search page
        prev_link = soup.select_one("a.btn.wide[href*='search']")
        if not prev_link or "上頁" not in prev_link.get_text():
            # Try the generic prev-page button
            prev_link = soup.select_one("#action-bar-container a[href*='search']")
        if not prev_link:
            break

        next_url = BASE_URL + prev_link["href"]
        if next_url == url:
            break
        url = next_url
        time.sleep(1.5)

    return posts


def scrape_post(url: str, client: httpx.Client) -> str | None:
    """Fetch a single PTT post and return its text content."""
    soup = fetch(url, client)
    if not soup:
        return None

    content_el = soup.select_one("#main-content")
    if not content_el:
        return None

    # Strip push/comment section — we only want the original post body
    for el in content_el.select(".push"):
        el.decompose()
    # Strip meta header (author, board, title lines at top)
    for el in content_el.select(".article-metaline, .article-metaline-right"):
        el.decompose()

    return content_el.get_text(separator="\n", strip=True)


def main(queries: list[str], max_pages: int = 5) -> None:
    out_path = RAW_DIR / "posts.json"

    # Resume support
    existing: list[dict] = []
    existing_urls: set[str] = set()
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        existing_urls = {p["url"] for p in existing}
        print(f"Resuming — {len(existing)} posts already scraped.")

    with httpx.Client(
        cookies=COOKIES,
        headers=HEADERS,
        verify=False,  # PTT occasionally has SSL cert issues
        follow_redirects=True,
    ) as client:
        # Phase 1: collect post metadata from search results
        all_posts: list[dict] = []
        seen_urls: set[str] = set()

        for query in queries:
            print(f"Searching PTT Gossiping for: 「{query}」")
            posts = scrape_search_results(query, client, max_pages)
            new = [p for p in posts if p["url"] not in seen_urls]
            seen_urls.update(p["url"] for p in new)
            all_posts.extend(new)
            print(f"  → {len(posts)} results, {len(new)} unique new | total: {len(all_posts)}")
            time.sleep(2)

        # Phase 2: fetch full post content for unseen posts
        to_fetch = [p for p in all_posts if p["url"] not in existing_urls]
        print(f"\nFetching {len(to_fetch)} new posts...")

        results = list(existing)
        for i, post in enumerate(to_fetch):
            print(f"[{i+1}/{len(to_fetch)}] {post['title'][:70]}")
            content = scrape_post(post["url"], client)
            if content:
                results.append({**post, "content": content})
                print(f"  → OK ({len(content)} chars)")
            else:
                print("  → skipped (no content)")
            time.sleep(1.5)

        out_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nSaved {len(results)} total posts to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape PTT Gossiping for fraud posts")
    parser.add_argument(
        "--queries",
        nargs="+",
        default=DEFAULT_QUERIES,
        help="Search keywords (zh-TW)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Max search result pages per query",
    )
    args = parser.parse_args()
    main(queries=args.queries, max_pages=args.max_pages)
