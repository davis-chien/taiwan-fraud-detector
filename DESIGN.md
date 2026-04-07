**Taiwan Fraud Detector**

System Design Document

Status: Draft — v0.1

Last updated: Tue Apr 07 2026

**1. Problem statement**

Elderly users in Taiwan receive suspicious URLs via LINE messages — from
friends, family, or strangers. They have no reliable, fast way to verify
if a link is safe before clicking. This app provides a simple web
interface where a user pastes a URL and receives a clear, plain-language
verdict.

**Target user**

- Primary: elderly users in Taiwan who receive LINE messages with
  suspicious links

- Secondary: family members who want to check a link on behalf of an
  elderly relative

**Core user story**

"I received a link in LINE that says I won a prize. I paste it here and
the app tells me in simple Chinese whether it is safe or a scam, and
why."

**2. Scope — MVP v1**

|                                          |                                        |
|------------------------------------------|----------------------------------------|
| **In scope (v1)**                        | **Out of scope (v2+)**                 |
| ✓ URL input via web app                  | — LINE bot integration                 |
| ✓ Taiwan/LINE-specific scam patterns KB  | — Real-time KB updates from news feeds |
| ✓ Hybrid RAG retriever (BM25 + semantic) | — Fine-tuning a custom model           |
| ✓ Structured JSON output + plain summary | — User accounts / history              |
| ✓ Static knowledge base (manual updates) | — Multi-language support beyond zh-TW  |
| ✓ Security hardening (layers 1–4)        | — Full container sandboxing (layer 5)  |
| ✓ Eval harness with labeled test set     | — Production monitoring dashboard      |
| ✓ Deployed on Hugging Face Spaces (free) | — Custom domain / paid hosting         |

**Constraints**

- Expected users: \<10 concurrent, MVP phase

- Knowledge base: static, manually updated every few months

- Deployment: Hugging Face Spaces (free tier), no dedicated infra

- Budget: minimal — free-tier APIs and open-source libraries where
  possible

**3. System architecture**

The system has six layers. Data flows top-to-bottom: URL → ingestion →
retrieval → reasoning → output → evaluation.

**3.1 Layer overview**

|                         |                                             |                                   |            |
|-------------------------|---------------------------------------------|-----------------------------------|------------|
| **Component**           | **Purpose**                                 | **Tech choice**                   | **Status** |
| **URL validator**       | Block SSRF, private IPs, bad schemes        | Python stdlib + ipaddress         | **v1**     |
| **Web scraper**         | Fetch page text, title, meta tags           | httpx + BeautifulSoup             | **v1**     |
| **URL unshortener**     | Resolve bit.ly / lin.ee redirects           | httpx follow-redirects            | **v1**     |
| **Domain enricher**     | WHOIS age, registrar country, typosquat     | python-whois + string analysis    | **v1**     |
| **Content sanitizer**   | Strip HTML, cap tokens, block prompt inject | BeautifulSoup + regex             | **v1**     |
| **BM25 keyword search** | Lexical match on fraud pattern KB           | rank_bm25                         | **v1**     |
| **Semantic search**     | Embedding similarity on fraud pattern KB    | ChromaDB + text-embedding-3-small | **v1**     |
| **Knowledge base**      | Taiwan/LINE scam pattern documents          | Markdown files in /kb/            | **v1**     |
| **Prompt builder**      | Assemble system + context + URL content     | Python f-strings / Jinja2         | **v1**     |
| **LLM reasoning**       | Analyze and produce structured verdict      | Claude Sonnet / GPT-4o            | **v1**     |
| **Output formatter**    | Parse JSON, render verdict + summary        | Pydantic schema validation        | **v1**     |
| **Gradio UI**           | Web interface, shareable link               | Gradio on HF Spaces               | **v1**     |
| **Eval harness**        | Measure precision/recall on labeled URLs    | Python script + CSV               | **v1**     |
| **LINE bot interface**  | Accept URLs directly in LINE                | LINE Messaging API                | **v2**     |
| **KB auto-update**      | Ingest new scam reports from 165 hotline    | Scheduled scraper + embedder      | **v2**     |

**3.2 Data flow**

- User pastes URL into Gradio web app

- Layer 1 — URL validator runs synchronously (0ms). Rejects private IPs,
  localhost, non-http schemes, cloud metadata endpoints, high-risk TLDs

- Layer 2 — URL unshortener resolves redirects (lin.ee, bit.ly). Max 3
  hops

- Layers 3+4 run in parallel via ThreadPoolExecutor:

  - Web scraper fetches page (5s connect timeout, 10s read, 2MB cap,
    subprocess isolated)

  - Domain enricher runs WHOIS lookup + domain pattern analysis (cached
    24h)

- Layer 5 — content sanitizer strips HTML to visible text only. Caps at
  3000 tokens

- RAG retriever runs hybrid search: BM25 keyword search + ChromaDB
  semantic search on knowledge base. Returns top-3 pattern documents

- Prompt builder assembles: system prompt + retrieved patterns +
  sanitized URL content

- LLM produces structured JSON output (enforced via JSON mode)

- Output formatter validates schema with Pydantic, renders verdict
  card + plain summary in Gradio

**3.3 Output schema**

The LLM is forced to return valid JSON matching this Pydantic schema on
every call:

class FraudVerdict(BaseModel): verdict: Literal\['fraud', 'suspicious',
'safe'\] confidence: float \# 0.0 – 1.0 matched_patterns: list\[str\] \#
KB pattern IDs signals: list\[str\] \# human-readable reasons
plain_summary: str \# simple Chinese for elderly users domain_age_days:
int \| None

**4. Security design**

Because the app fetches arbitrary URLs submitted by users, it is a
potential target for SSRF and prompt injection. Four defense layers are
implemented in v1. A fifth (container sandboxing) is deferred to v2.

|                  |                                                   |                                                                                                                                                                         |               |
|------------------|---------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|
| **Layer**        | **Threat blocked**                                | **Implementation**                                                                                                                                                      | **Cost**      |
| **Layer 1**      | SSRF — private IP / internal endpoint access      | Block private IP ranges (10.x, 192.168.x, 172.16.x, 127.x), localhost, AWS/GCP metadata endpoints (169.254.169.254), non-http schemes. Pure Python, zero network calls. | ~0ms          |
| **Layer 2**      | Redirect abuse, timeout/hang, oversized responses | httpx in subprocess. 5s connect timeout, 10s read timeout, 2MB response cap, max 3 redirects. Subprocess hard-killed by OS after 15s.                                   | ~0ms overhead |
| **Layer 3**      | Prompt injection via hidden HTML content          | Strip all tags, extract visible text only via BeautifulSoup. Cap at 3000 tokens. Hidden comments and invisible divs never reach the LLM.                                | ~0ms          |
| **Layer 4**      | Redirect to private IP after DNS resolution       | Resolve hostname to IP before fetching. Re-check resolved IP against private ranges (DNS rebinding defense).                                                            | ~50ms         |
| **Layer 5 (v2)** | Scraper crash affects main app                    | Run scraper in dedicated Docker container per request. Adds 2–5s cold start. Deferred — subprocess isolation sufficient for MVP scale.                                  | 2–5s          |

**5. Knowledge base**

**5.1 Structure**

Each pattern is a markdown file in /knowledge_base/. Filename = pattern
ID. Both BM25 and ChromaDB index from the same files on startup.

knowledge_base/ tw_investment_scam.md tw_line_gift_card.md
tw_fake_delivery.md tw_romance_scam.md tw_installment_cancellation.md
tw_fake_bank_login.md ...

**5.2 Pattern document format**

\# Pattern ID: tw_line_gift_card \## Name: LINE gift card scam
(線上禮品卡詐騙) \## Category: messaging_platform_scam \## Risk level:
high \## Description Scammer hijacks a victim’s LINE account and
messages their contacts asking them to buy convenience store gift cards
(7-Eleven, FamilyMart) and send photos of the redemption codes. \## Red
flag signals - Urgent request to buy gift cards from a “friend” -
Request made via LINE message - Asks for card codes or photos of the
card back - Sender cannot video call or seems evasive \## Keywords
(zh-TW) 礙券, 禮品卡, 7-11, 全家, 游戲點數, 儲値卡

**5.3 Taiwan scam categories to cover (v1)**

- tw_fake_bank_login — phishing pages impersonating Taiwan banks
  (土地銀行, 台灣銀行, 玉山銀行)

- tw_line_gift_card — LINE account hijack + gift card request

- tw_investment_scam — fake high-return investment platforms
  (假投資詐騙)

- tw_fake_delivery — fake 黑貓/7-11 delivery fee pages

- tw_installment_cancellation — fake bank calls about accidental
  installment plans (解除分期付款)

- tw_romance_scam — long-game relationship scams that eventually ask for
  money

- tw_lottery_prize — you won a prize, pay a small processing fee

- tw_government_impersonation — fake NHI / police / court notifications

Target: 20–30 pattern documents for v1. Source: 165反詐騙諮詢專線 case
reports, Criminal Investigation Bureau annual statistics.

**6. Tech stack**

|                     |                        |                                                                                               |
|---------------------|------------------------|-----------------------------------------------------------------------------------------------|
| **Component**       | **Choice**             | **Rationale**                                                                                 |
| **UI**              | Gradio                 | Zero frontend code. Free public link via Hugging Face Spaces. Supports Chinese text.          |
| **Web scraper**     | httpx + BeautifulSoup  | Async-capable, handles redirects, lightweight. subprocess wrapper for isolation.              |
| **Domain enricher** | python-whois           | WHOIS lookup in pure Python. Cache results 24h with functools.lru_cache or Redis later.       |
| **Keyword search**  | rank_bm25              | BM25 in pure Python, zero infra, indexes on startup from markdown files.                      |
| **Vector store**    | ChromaDB (in-memory)   | No server needed for MVP. Persists to local file. Upgrade to hosted Chroma or Pinecone in v2. |
| **Embeddings**      | text-embedding-3-small | OpenAI. Multilingual, cheap (~\$0.02/1M tokens). Handles zh-TW well.                          |
| **LLM**             | Claude Sonnet 4.5      | Strong structured output. JSON mode enforced. Fallback: GPT-4o.                               |
| **Output schema**   | Pydantic v2            | Validates LLM JSON output. Hard fails if schema violated — no silent garbage.                 |
| **Deployment**      | Hugging Face Spaces    | Free, public URL, git-based deploy. Sufficient for \<10 users.                                |
| **Eval**            | Python + pandas + CSV  | Simple eval loop. No MLflow needed at this scale.                                             |
| **KB format**       | Markdown files in /kb/ | Human-editable, git-tracked, no DB migration when adding patterns.                            |

**7. Open questions**

Items to decide before or during implementation:

**\[ \]** Should the plain_summary be generated in Traditional Chinese
(zh-TW) by default, or English, or user-selectable?

**\[ \]** How to handle JavaScript-heavy pages (SPAs) where httpx
returns empty content? Options: Playwright headless browser (heavier),
or skip with a clear error message.

**\[ \]** What is the confidence threshold for 'suspicious' vs 'fraud'
vs 'safe'? Needs calibration against eval set.

**\[ \]** Which LLM to use as primary — Claude Sonnet vs GPT-4o? Cost,
rate limits, and zh-TW quality need comparison test.

**\[ \]** How to source labeled fraud URLs for the eval harness?
Candidates: 165 hotline reports, g0v community data, manual collection.

**\[ \]** WHOIS lookup sometimes returns no data for .tw domains.
Fallback strategy needed.

**\[ \]** Should the Gradio app support pasting raw text (not just URLs)
as v1.5 feature?

**8. Decisions log**

Rationale captured for major design choices:

**Input: URL only (not pasted text):** Simpler UX for elderly users. App
fetches content automatically behind the scenes.

**KB: static fraud patterns (not labeled examples):** Faster to build,
easier to explain, maps directly to RAG course learning. Labeled
examples added in v2.

**KB: markdown files (not a DB):** Human-editable, git-tracked, zero
migration cost when adding patterns.

**Retriever: hybrid BM25 + semantic:** BM25 catches exact zh-TW scam
terminology; semantic catches paraphrases. Neither alone is sufficient.

**Security: layers 1–4 only in v1:** Container sandboxing (layer 5) adds
2–5s latency. Overkill for MVP with \<10 users. Process isolation
sufficient.

**Deployment: Hugging Face Spaces:** Free, public URL, no infra ops.
Upgrade to Railway or Fly.io if scale demands it.

**Output: Pydantic-validated JSON:** Prevents silent schema violations.
Fail loudly if LLM returns unexpected format.

**Domain enricher: parallel with scraper:** WHOIS ~1s, scrape ~5–8s.
Running concurrently saves wall-clock time at zero cost.

**9. Iteration history**

|             |          |                                                                                                                                                           |
|-------------|----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Version** | **Date** | **Changes**                                                                                                                                               |
| v0.1        | 4/7/2026 | Initial design. Problem statement, MVP scope, 6-layer architecture, security model (layers 1–4), KB structure, tech stack, open questions, decisions log. |

*Next iteration: scope knowledge base content (Taiwan scam categories),
then move to implementation.*
