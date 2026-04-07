# Taiwan Fraud Detector 台灣詐騙網址偵測器

> A RAG-based web application that analyzes URLs shared via LINE to detect fraud targeting elderly users in Taiwan.

**Status:** In progress — design phase complete, implementation starting  
**Demo:** *(coming soon — Hugging Face Spaces)*  
**Design doc:** [DESIGN.md](./DESIGN.md)

---

## What it does

Users paste a URL they received in a LINE message. The app:

1. Fetches and analyzes the page content
2. Retrieves the most relevant Taiwan scam patterns from a knowledge base
3. Asks an LLM to reason about the evidence
4. Returns a verdict (fraud / suspicious / safe), confidence score, and a plain-language summary in Traditional Chinese

## Architecture overview

```
URL input
    │
    ▼
Security layer (SSRF block, sanitize, unshorten)
    │
    ├─── Web scraper (httpx + BeautifulSoup)
    └─── Domain enricher (WHOIS age, registrar, typosquat)  ← parallel
    │
    ▼
Hybrid RAG retriever
    ├─── BM25 keyword search (rank_bm25)
    └─── Semantic search (ChromaDB + OpenAI embeddings)
    │
    ▼
Knowledge base (Taiwan/LINE scam patterns — markdown)
    │
    ▼
Prompt builder → LLM (Claude Sonnet)
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

Accuracy measured against a labeled test set of ~80 Taiwan fraud and legitimate URLs. Results documented in [`eval/results.csv`](./eval/) as the project develops.

## Project structure

```
taiwan-fraud-detector/
├── README.md
├── DESIGN.md              # Living system design document
├── app.py                 # Gradio app entry point
├── pipeline/
│   ├── validator.py       # URL validation + SSRF defense
│   ├── scraper.py         # Web scraper (subprocess isolated)
│   ├── enricher.py        # Domain enricher (WHOIS)
│   ├── sanitizer.py       # Content sanitizer
│   ├── retriever.py       # Hybrid BM25 + semantic search
│   ├── prompt_builder.py  # Augmented prompt assembly
│   └── output.py          # Pydantic schema + formatter
├── knowledge_base/        # Taiwan scam pattern markdown files
├── eval/
│   ├── eval.py            # Evaluation harness
│   ├── labeled_urls.csv   # Ground truth test set
│   └── results.csv        # Eval results by prompt version
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

*Data sources for knowledge base: [165反詐騙諮詢專線](https://165.npa.gov.tw/), Criminal Investigation Bureau annual fraud statistics.*
