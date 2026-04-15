"""
Scrape TWCERT/CC security news for phishing and fraud alerts.

Source: https://www.twcert.org.tw/tw/lp-104-1.html
Output: scrapers/raw/twcert/articles.json

Usage:
    python scrapers/scrape_twcert.py
    python scrapers/scrape_twcert.py --max-pages 5
"""

import argparse
import json
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.twcert.org.tw"
NEWS_LIST_TEMPLATE = BASE_URL + "/tw/lp-104-{page}.html"

# Keywords that indicate fraud/phishing content
FRAUD_KEYWORDS = [
    "釣魚", "詐騙", "假冒", "網路詐欺", "惡意連結",
    "phishing", "scam", "fraud", "social engineering",
    "勒索", "帳號盜用", "個資外洩",
]

RAW_DIR = Path(__file__).parent / "raw" / "twcert"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
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


def is_fraud_related(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in FRAUD_KEYWORDS)


def scrape_article_list(client: httpx.Client, max_pages: int) -> list[dict]:
    """Scrape the news listing pages and return article metadata."""
    articles = []
    for page in range(1, max_pages + 1):
        url = NEWS_LIST_TEMPLATE.format(page=page)
        print(f"  Fetching listing page {page}: {url}")
        soup = fetch(url, client)
        if soup is None:
            break

        # TWCERT news items appear in .item or article elements
        items = (
            soup.select(".contentItem")
            or soup.select(".item-list li")
            or soup.select("article")
        )
        if not items:
            print(f"  No items found on page {page}, stopping.")
            break

        found_on_page = 0
        for item in items:
            a = item.find("a", href=True)
            if not a:
                continue
            title = a.get_text(strip=True) or item.get_text(strip=True)
            href = a["href"]
            if not href.startswith("http"):
                href = BASE_URL + href
            date_el = item.select_one("time, .date, [class*='date']")
            date = date_el.get_text(strip=True) if date_el else ""
            articles.append({"title": title, "url": href, "date": date})
            found_on_page += 1

        print(f"    → {found_on_page} articles found")
        time.sleep(1.5)

    return articles


def scrape_article(url: str, client: httpx.Client) -> dict | None:
    """Fetch and extract content from a single TWCERT article page."""
    soup = fetch(url, client)
    if not soup:
        return None

    title_el = soup.select_one("h1, h2.title, .article-title")
    date_el = soup.select_one("time, .date, [class*='pubdate'], [class*='date']")

    # Main content — try common selectors in order of specificity
    content_el = (
        soup.select_one(".content-detail")
        or soup.select_one(".article-content")
        or soup.select_one("#main-content")
        or soup.select_one("main")
        or soup.select_one("article")
    )
    if not content_el:
        return None

    # Remove navigation, scripts, and style noise
    for tag in content_el.select("nav, script, style, .breadcrumb, .pager"):
        tag.decompose()

    return {
        "url": url,
        "title": title_el.get_text(strip=True) if title_el else "",
        "date": date_el.get_text(strip=True) if date_el else "",
        "content": content_el.get_text(separator="\n", strip=True),
        "source": "TWCERT/CC",
    }


def main(max_pages: int = 10) -> None:
    out_path = RAW_DIR / "articles.json"

    # Load existing results to allow resuming
    existing: list[dict] = []
    existing_urls: set[str] = set()
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        existing_urls = {a["url"] for a in existing}
        print(f"Resuming — {len(existing)} articles already scraped.")

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        print("Fetching TWCERT article listing...")
        all_articles = scrape_article_list(client, max_pages)
        print(f"Total articles found: {len(all_articles)}")

        fraud_articles = [a for a in all_articles if is_fraud_related(a["title"])]
        new_articles = [a for a in fraud_articles if a["url"] not in existing_urls]
        print(
            f"Fraud-related: {len(fraud_articles)} | "
            f"New (not yet scraped): {len(new_articles)}"
        )

        results = list(existing)
        for i, article in enumerate(new_articles):
            print(f"[{i+1}/{len(new_articles)}] {article['title'][:70]}")
            data = scrape_article(article["url"], client)
            if data:
                results.append(data)
                print(f"  → OK ({len(data['content'])} chars)")
            else:
                print("  → skipped (no content)")
            time.sleep(1.5)

        out_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nSaved {len(results)} total articles to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape TWCERT/CC fraud alerts")
    parser.add_argument(
        "--max-pages", type=int, default=10, help="Max listing pages to crawl"
    )
    args = parser.parse_args()
    main(max_pages=args.max_pages)
