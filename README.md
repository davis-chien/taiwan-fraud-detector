# Taiwan Fraud Detector 台灣詐騙訊息偵測器

> A RAG-based web application that analyzes full LINE messages to detect fraud targeting elderly users in Taiwan.

**Status:** Phase 1 local MVP complete — safe LINE message analysis, URL extraction, validation, and a Gradio UI are implemented.  
**Demo:** Run locally with `python3 app.py` and open `http://127.0.0.1:7860`  
**Design doc:** [DESIGN.md](./DESIGN.md)

---

## What it does

Elderly users in Taiwan receive fraudulent LINE messages but often cannot copy just the URL. Instead, they can **forward the whole message** — the same way they'd share it to a friend. The app accepts the full message text and:

1. Analyzes the message wording for fraud signals (urgency, impersonation, bait language)
2. Extracts any URLs from the message (if present)
3. Fetches and analyzes the linked page content (URL branch only)
4. Retrieves the most relevant Taiwan scam patterns from a knowledge base
5. Asks an LLM to reason over all evidence
6. Returns a verdict (fraud / suspicious / safe), confidence score, and a plain-language summary in Traditional Chinese

**Works with or without a URL.** Text-only fraud messages (gift card requests, impersonation scripts, urgency bait) are analyzed on message wording alone.

## Architecture overview

```
Full LINE message (text)
    │
    ▼
Message sanitizer (prompt injection defense)
    │
    ▼
Message signal analyzer (urgency / impersonation / bait keywords)
    │
    ▼
URL extractor
    │
    ├── URL found ──────────────────────────────────────────────────┐
    │                                                               │
    │   URL validator + unshortener (SSRF block, resolve lin.ee)   │
    │       │                                                       │
    │       ├─── Web scraper (httpx + BeautifulSoup)  ← parallel   │
    │       └─── Domain enricher (WHOIS, typosquat)   ← parallel   │
    │                                                               │
    └── No URL ──────────────────────────────────────────────────┐  │
                                                                 ▼  ▼
                                                    Hybrid RAG retriever
                                                    (query = message text [+ page content if URL])
                                                        ├─── BM25 keyword search
                                                        └─── Semantic search (ChromaDB)
                                                                 │
                                                                 ▼
                                                    Knowledge base (Taiwan/LINE scam patterns)
                                                                 │
                                                                 ▼
                                                    Prompt builder → LLM (Claude Sonnet 4.6)
                                                                 │
                                                                 ▼
                                                    Structured output (Pydantic-validated JSON)
                                                                 │
                                                                 ▼
                                                          Gradio web UI
```

## Tech stack

| Layer | Choice |
|---|---|
| UI | Gradio on Hugging Face Spaces |
| Scraper | httpx + BeautifulSoup |
| Keyword search | rank_bm25 |
| Vector store | ChromaDB (in-memory) |
| Embeddings | OpenAI text-embedding-3-small |
| LLM | Claude Sonnet |
| Output schema | Pydantic v2 |
| Deployment | Hugging Face Spaces (free) |

## Scam categories covered

- Fake bank login pages (phishing)
- LINE gift card scams (帳號盜用)
- Fake investment platforms (假投資詐騙)
- Fake delivery fee pages (假包裹通知)
- Installment cancellation scams (解除分期付款)
- Romance scams
- Lottery / prize scams
- Government impersonation (假冒健保署 / 警察)

## Security

Four defense layers protect the app from SSRF, prompt injection, and resource exhaustion. See [DESIGN.md §4](./DESIGN.md#4-security-design) for details.

## Evaluation

Precision and recall measured against a labeled test set of ~100 real Taiwan fraud LINE messages. Recall is the primary optimization target — missing a fraud causes real harm; false alarms are merely annoying.

Results documented in [`eval/results.csv`](./eval/) as the project develops.

## Project structure

```
taiwan-fraud-detector/
├── README.md
├── DESIGN.md                  # Living system design document
├── app.py                     # Gradio app entry point
├── pipeline/
│   ├── extractor.py           # URL extraction from message text
│   ├── validator.py           # URL validation + SSRF defense
│   ├── scraper.py             # Web scraper (subprocess isolated)
│   ├── enricher.py            # Domain enricher (WHOIS)
│   ├── sanitizer.py           # Content sanitizer (page + message)
│   ├── retriever.py           # Hybrid BM25 + semantic search
│   ├── prompt_builder.py      # Augmented prompt assembly
│   └── output.py              # Pydantic schema + formatter
├── knowledge_base/            # Taiwan scam pattern markdown files
├── scrapers/
│   ├── scrape_165.py          # Scrape 165.npa.gov.tw fraud cases
│   ├── scrape_ptt.py          # Scrape PTT community fraud posts
│   ├── scrape_news.py         # Scrape CNA/UDN fraud news articles
│   ├── scrape_twcert.py       # Scrape TWCERT phishing alerts
│   ├── build_kb.py            # Convert reviewed scrapes → KB markdown
│   └── raw/                   # Raw scrape dumps (git-ignored)
├── eval/
│   ├── eval.py                # Evaluation harness
│   ├── labeled_messages.csv   # Ground truth test set (full LINE messages)
│   └── results.csv            # Eval results by prompt version
└── requirements.txt
```

## Running locally

```bash
git clone https://github.com/davis-chien/taiwan-fraud-detector
cd taiwan-fraud-detector
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key
export OPENAI_API_KEY=your_key
python app.py
```

## Learning context

This project is built as a practical AI engineering portfolio piece while completing the DeepLearning.AI RAG course. It demonstrates: RAG architecture, hybrid retrieval, prompt engineering, structured LLM output, security hardening, and evaluation methodology.

---

*Data sources: [165反詐騙諮詢專線](https://165.npa.gov.tw/), [TWCERT/CC](https://www.twcert.org.tw/), PTT community posts, CNA/UDN news articles quoting fraud messages, Criminal Investigation Bureau annual statistics.*
