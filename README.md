---
title: Taiwan Fraud Detector
emoji: 🔍
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# Taiwan Fraud Detector 台灣詐騙訊息偵測器

> A RAG-based web application that analyzes full LINE messages to detect fraud targeting elderly users in Taiwan.

**Status:** Phase 4 code complete — containerized, fetcher isolated, egress policy applied. HF Spaces deployment pending. Phase 5 planned: eval expansion, KB expansion, ablation study, LLM and embeddings model comparison, confidence calibration.  
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
| UI | Gradio (Docker container, port 7860) |
| Fetcher worker | FastAPI service — isolates URL fetch / unshorten / WHOIS in a separate container |
| Scraper | httpx + BeautifulSoup |
| Keyword search | rank_bm25 |
| Vector store | ChromaDB (in-memory) |
| Embeddings | Voyage AI voyage-multilingual-2 |
| LLM | Claude Sonnet 4.6 (`claude-sonnet-4-6`) |
| Output schema | Pydantic v2 |
| Deployment | Hugging Face Spaces — Docker SDK (pending) |

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

Six defense layers protect the app from SSRF, prompt injection, and resource exhaustion. See [DESIGN.md §4](./DESIGN.md#4-security-design) for details.

## Evaluation

Precision and recall measured against a labeled test set. Current seed set: 25 messages (15 fraud across 8 categories, 8 safe, 2 suspicious). Target for v2: ~100 messages. Recall is the primary optimization target — missing a fraud causes real harm; false alarms are merely annoying.

Local test coverage is organized by component, with dedicated files for each pipeline module and end-to-end app integration. See `tests/test_sanitizer.py`, `tests/test_extractor.py`, `tests/test_validator.py`, `tests/test_signal_analyzer.py`, `tests/test_unshortener.py`, `tests/test_url_signals.py`, `tests/test_url_metadata.py`, and `tests/test_app.py`.

Results documented in [`eval/results.csv`](./eval/) as the project develops.

## Project structure

```
taiwan-fraud-detector/
├── README.md
├── DESIGN.md                    # Living system design document
├── Dockerfile                   # Main app container (HF Spaces / Docker)
├── docker-compose.yml           # Orchestrates app + fetcher worker
├── .dockerignore
├── app.py                       # Gradio app entry point
├── requirements.txt
├── pipeline/
│   ├── extractor.py             # URL extraction from message text
│   ├── validator.py             # URL validation + SSRF defense
│   ├── sanitizer.py             # Message + page content sanitizer
│   ├── signal_analyzer.py       # Message fraud signal detection
│   ├── url_signals.py           # URL-origin heuristic signals
│   ├── url_metadata.py          # URL metadata extraction
│   ├── unshortener.py           # URL unshortening + per-hop SSRF check
│   ├── scraper.py               # Web scraper (subprocess isolated)
│   ├── enricher.py              # Domain enricher (WHOIS, 24h cache)
│   ├── retriever.py             # Hybrid BM25 + semantic search
│   ├── prompt_builder.py        # Augmented prompt assembly
│   ├── llm.py                   # Claude Sonnet 4.6 via forced tool use
│   ├── output.py                # Pydantic schema + formatter
│   └── fetcher_client.py        # HTTP client for fetcher worker
├── fetcher/
│   ├── main.py                  # FastAPI fetcher worker
│   ├── Dockerfile               # Fetcher container (iptables egress policy)
│   ├── entrypoint.sh            # iptables setup + gosu privilege drop
│   └── requirements.txt
├── tests/
│   ├── test_app.py              # App integration coverage
│   ├── test_extractor.py
│   ├── test_sanitizer.py
│   ├── test_signal_analyzer.py
│   ├── test_unshortener.py
│   ├── test_url_signals.py
│   ├── test_url_metadata.py
│   ├── test_validator.py
│   ├── test_enricher.py
│   ├── test_scraper.py
│   ├── test_retriever.py
│   ├── test_prompt_builder.py
│   ├── test_llm.py
│   └── test_output.py
├── knowledge_base/              # Taiwan scam pattern markdown files
├── scrapers/
│   ├── scrape_165.py            # Scrape 165.npa.gov.tw fraud cases
│   ├── scrape_ptt.py            # Scrape PTT community fraud posts
│   ├── scrape_news.py           # Scrape CNA/UDN fraud news articles
│   ├── scrape_twcert.py         # Scrape TWCERT phishing alerts
│   ├── build_kb.py              # Convert reviewed scrapes → KB markdown
│   └── raw/                     # Raw scrape dumps (git-ignored)
└── eval/
    ├── eval.py                  # Evaluation harness
    ├── labeled_messages.csv     # Ground truth test set (full LINE messages)
    └── results.csv              # Eval results by prompt version
```

## Running locally

```bash
git clone https://github.com/davis-chien/taiwan-fraud-detector
cd taiwan-fraud-detector
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key
export VOYAGE_API_KEY=your_key   # optional — enables semantic search; falls back to BM25
python app.py
```

## Deploying to Hugging Face Spaces

This repo is configured as a **Docker Space** (`sdk: docker`, `app_port: 7860`). To deploy:

1. Create a new Space at huggingface.co → "Docker" SDK.
2. Push this repo as the Space repo (or link it via HF git remote).
3. Set the following secrets in the Space settings:
   - `ANTHROPIC_API_KEY` — required for LLM inference
   - `VOYAGE_API_KEY` — optional, enables semantic search alongside BM25

HF Spaces will build the `Dockerfile` automatically and expose port 7860.

## Running with Docker Compose (recommended)

Starts the Gradio app and the isolated fetcher worker as separate containers:

```bash
ANTHROPIC_API_KEY=your_key VOYAGE_API_KEY=your_key docker compose up --build
```

The app is available at `http://localhost:7860`. The fetcher worker runs internally on port 8080 and is not exposed to the host.

## Running the app container only (no fetcher isolation)

```bash
docker build -t taiwan-fraud-detector .
docker run -p 7860:7860 \
  -e ANTHROPIC_API_KEY=your_key \
  -e VOYAGE_API_KEY=your_key \
  taiwan-fraud-detector
```

Without `FETCHER_URL` set, URL fetch operations fall back to in-process subprocess calls.

## Learning context

This project is built as a practical AI engineering portfolio piece while completing the DeepLearning.AI RAG course. It demonstrates: RAG architecture, hybrid retrieval, prompt engineering, structured LLM output, security hardening, and evaluation methodology.

---

*Data sources: [165反詐騙諮詢專線](https://165.npa.gov.tw/), [TWCERT/CC](https://www.twcert.org.tw/), PTT community posts, CNA/UDN news articles quoting fraud messages, Criminal Investigation Bureau annual statistics.*
