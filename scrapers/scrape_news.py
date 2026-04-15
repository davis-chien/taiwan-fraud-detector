"""
Scrape Taiwan news sites for fraud-related articles.

News articles frequently quote verbatim fraud messages, making them a
high-quality source of authentic 話術 (scripts) with editorial validation.

Sources:
  - CNA (Central News Agency / 中央社): Taiwan's official news agency
  - UDN (聯合新聞網): Major commercial news outlet

Output: scrapers/raw/news/articles.json

Usage:
    python scrapers/scrape_news.py
    python scrapers/scrape_news.py --source cna --max-pages 5
"""

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup

RAW_DIR = Path(__file__).parent / "raw" / "news"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

SEARCH_QUERIES = [
    "詐騙LINE",
    "假冒銀行詐騙",
    "假包裹詐騙",
    "假投資詐騙",
    "假冒警察詐騙",
    "解除分期詐騙",
    "假冒健保署",
    "釣魚網站台灣",
]


# ---------------------------------------------------------------------------
# CNA (Central News Agency) — https://www.cna.com.tw
# ---------------------------------------------------------------------------

CNA_SEARCH_URL = "https://www.cna.com.tw/search/hissearch.aspx"


def fetch(url: str, client: httpx.Client, **kwargs) -> BeautifulSoup | None:
    try:
        resp = client.get(url, timeout=20, **kwargs)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except httpx.HTTPStatusError as e:
        print(f"  [WARN] HTTP {e.response.status_code} for {url}")
        return None
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return None


def scrape_cna_search(
    query: str, client: httpx.Client, max_pages: int
) -> list[dict]:
    """Search CNA for a keyword and return article metadata."""
    articles = []
    for page in range(1, max_pages + 1):
        params = {"q": query, "pageNo": page}
        url = f"{CNA_SEARCH_URL}?{urlencode(params)}"
        soup = fetch(url, client)
        if not soup:
            break

        items = soup.select(".item") or soup.select(".searchResult li") or []
        if not items:
            break

        for item in items:
            a = item.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            if not href.startswith("http"):
                href = urljoin("https://www.cna.com.tw", href)
            title = a.get_text(strip=True)
            date_el = item.select_one(".date, time")
            articles.append({
                "title": title,
                "url": href,
                "date": date_el.get_text(strip=True) if date_el else "",
                "source": "CNA",
                "query": query,
            })

        time.sleep(1.5)

    return articles


def scrape_cna_article(url: str, client: httpx.Client) -> str | None:
    """Extract article body from a CNA article page."""
    soup = fetch(url, client)
    if not soup:
        return None

    content_el = (
        soup.select_one(".paragraph")
        or soup.select_one("article .content")
        or soup.select_one("#jsMainContent")
        or soup.select_one(".centralContent")
    )
    if not content_el:
        return None

    for tag in content_el.select("script, style, .ad, .related"):
        tag.decompose()

    return content_el.get_text(separator="\n", strip=True)


# ---------------------------------------------------------------------------
# UDN (聯合新聞網) — https://udn.com
# ---------------------------------------------------------------------------

UDN_SEARCH_URL = "https://udn.com/search/result/2/{query}"


def scrape_udn_search(
    query: str, client: httpx.Client, max_pages: int
) -> list[dict]:
    """Search UDN for a keyword and return article metadata."""
    articles = []
    for page in range(1, max_pages + 1):
        url = UDN_SEARCH_URL.format(query=query)
        if page > 1:
            url += f"?page={page}"
        soup = fetch(url, client)
        if not soup:
            break

        items = (
            soup.select(".story-list__news")
            or soup.select(".search-result-item")
            or []
        )
        if not items:
            break

        for item in items:
            a = item.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            if not href.startswith("http"):
                href = urljoin("https://udn.com", href)
            title_el = item.select_one("h2, h3, .title")
            date_el = item.select_one("time, .article-time")
            articles.append({
                "title": title_el.get_text(strip=True) if title_el else a.get_text(strip=True),
                "url": href,
                "date": date_el.get_text(strip=True) if date_el else "",
                "source": "UDN",
                "query": query,
            })

        time.sleep(1.5)

    return articles


def scrape_udn_article(url: str, client: httpx.Client) -> str | None:
    """Extract article body from a UDN article page."""
    soup = fetch(url, client)
    if not soup:
        return None

    content_el = (
        soup.select_one(".article-content__editor")
        or soup.select_one(".story-body-content")
        or soup.select_one("#story_body_content")
    )
    if not content_el:
        return None

    for tag in content_el.select("script, style, .ad"):
        tag.decompose()

    return content_el.get_text(separator="\n", strip=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SCRAPERS = {
    "cna": (scrape_cna_search, scrape_cna_article),
    "udn": (scrape_udn_search, scrape_udn_article),
}


def main(sources: list[str], max_pages: int = 5) -> None:
    out_path = RAW_DIR / "articles.json"

    existing: list[dict] = []
    existing_urls: set[str] = set()
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        existing_urls = {a["url"] for a in existing}
        print(f"Resuming — {len(existing)} articles already scraped.")

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        all_meta: list[dict] = []
        seen_urls: set[str] = set()

        for source in sources:
            search_fn, _ = SCRAPERS[source]
            for query in SEARCH_QUERIES:
                print(f"[{source.upper()}] Searching: 「{query}」")
                results = search_fn(query, client, max_pages)
                new = [r for r in results if r["url"] not in seen_urls]
                seen_urls.update(r["url"] for r in new)
                all_meta.extend(new)
                print(f"  → {len(results)} results, {len(new)} unique new | total: {len(all_meta)}")
                time.sleep(2)

        to_fetch = [a for a in all_meta if a["url"] not in existing_urls]
        print(f"\nFetching content for {len(to_fetch)} new articles...")

        results = list(existing)
        for i, article in enumerate(to_fetch):
            _, article_fn = SCRAPERS[article["source"].lower()]
            print(f"[{i+1}/{len(to_fetch)}] [{article['source']}] {article['title'][:65]}")
            content = article_fn(article["url"], client)
            if content:
                results.append({**article, "content": content})
                print(f"  → OK ({len(content)} chars)")
            else:
                print("  → skipped (no content)")
            time.sleep(1.5)

        out_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nSaved {len(results)} total articles to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Taiwan news for fraud articles")
    parser.add_argument(
        "--source",
        choices=["cna", "udn", "all"],
        default="all",
        help="News source to scrape",
    )
    parser.add_argument(
        "--max-pages", type=int, default=5, help="Max search result pages per query"
    )
    args = parser.parse_args()
    sources = ["cna", "udn"] if args.source == "all" else [args.source]
    main(sources=sources, max_pages=args.max_pages)
