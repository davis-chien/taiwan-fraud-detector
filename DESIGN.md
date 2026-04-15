**Taiwan Fraud Detector**

System Design Document

Status: Draft — v0.2

Last updated: Wed Apr 15 2026

---

**1. Problem statement**

Elderly users in Taiwan receive fraudulent LINE messages containing suspicious URLs — from strangers, hijacked friend accounts, or imposters of known institutions (banks, police, couriers). They have no reliable way to verify whether a message is a scam before clicking its link.

The core UX challenge: elderly users often cannot isolate and copy only the URL portion of a LINE message. However, they *can* forward or share an entire message — the same gesture used to share messages to friends or other apps on LINE.

This app accepts the full LINE message text (containing a URL and surrounding wording), analyzes both the URL and the message content, and returns a clear plain-language verdict in Traditional Chinese.

**Target user**

- Primary: elderly users in Taiwan who receive LINE messages with suspicious links
- Secondary: family members checking a message on behalf of an elderly relative

**Core user story**

"I received a LINE message that says I won a prize. I forward the whole message here and the app tells me in simple Chinese whether it is safe or a scam, and why."

---

**2. Scope — MVP v1**

| **In scope (v1)** | **Out of scope (v2+)** |
|---|---|
| ✓ Full LINE message input (text area in Gradio) | — LINE bot integration |
| ✓ URL extraction from message text (if present) | — Real-time KB updates from news feeds |
| ✓ Message wording analysis (urgency, impersonation, bait signals) | — Full LINE chat history analysis |
| ✓ Verdict for messages with no URL (text-only fraud signals) | — Fine-tuning a custom model |
| ✓ Taiwan/LINE-specific scam patterns knowledge base | — User accounts / history |
| ✓ Semi-automated KB scraping (165.gov.tw, PTT, news) | — Multi-language support beyond zh-TW |
| ✓ Hybrid RAG retriever (BM25 + semantic) | — Full container sandboxing (layer 5) |
| ✓ Structured JSON output + plain summary in zh-TW | — Production monitoring dashboard |
| ✓ Security hardening (layers 0–4) | — Custom domain / paid hosting |
| ✓ Eval harness with precision/recall on labeled messages | |
| ✓ Deployed on Hugging Face Spaces (free) | |

**Constraints**

- Expected users: <10 concurrent, MVP phase
- Knowledge base: semi-automated scraping from public sources, refreshed manually
- Deployment: Hugging Face Spaces (free tier), no dedicated infra
- Budget: minimal — free-tier APIs and open-source libraries where possible

---

**3. System architecture**

Data flows top-to-bottom: full LINE message → sanitize input → extract URL → analyze message → fetch URL content → retrieve KB patterns → LLM reasoning → structured output.

**3.1 Layer overview**

| **Component** | **Purpose** | **Tech choice** | **Status** |
|---|---|---|---|
| **Message sanitizer** | Strip prompt injection from raw message input | regex + deny-list | **v1** |
| **URL extractor** | Parse URLs from free-form message text | Python regex + urllib | **v1** |
| **Message signal analyzer** | Extract urgency, impersonation, gift/threat keywords | regex + zh-TW keyword lists | **v1** |
| **URL validator** | Block SSRF, private IPs, bad schemes | Python stdlib + ipaddress | **v1** |
| **URL unshortener** | Resolve bit.ly / lin.ee redirects | httpx follow-redirects | **v1** |
| **Web scraper** | Fetch page text, title, meta tags | httpx + BeautifulSoup | **v1** |
| **Domain enricher** | WHOIS age, registrar country, typosquat | python-whois + string analysis | **v1** |
| **Content sanitizer** | Strip HTML, cap tokens, block prompt inject from page | BeautifulSoup + regex | **v1** |
| **BM25 keyword search** | Lexical match on fraud pattern KB | rank_bm25 | **v1** |
| **Semantic search** | Embedding similarity on fraud pattern KB | ChromaDB + text-embedding-3-small | **v1** |
| **Knowledge base** | Taiwan/LINE scam pattern documents | Markdown files in /knowledge_base/ | **v1** |
| **Prompt builder** | Assemble system + message signals + URL content + KB patterns | Python f-strings / Jinja2 | **v1** |
| **LLM reasoning** | Analyze and produce structured verdict | Claude Sonnet 4.6 | **v1** |
| **Output formatter** | Parse JSON, render verdict + summary | Pydantic v2 | **v1** |
| **Gradio UI** | Web interface, shareable link | Gradio on HF Spaces | **v1** |
| **Eval harness** | Measure precision/recall on labeled messages | Python + pandas + CSV | **v1** |
| **KB scraper** | Semi-automated scraping from 165.gov.tw, PTT, news | httpx + BeautifulSoup | **v1** |
| **LINE bot interface** | Accept messages directly in LINE | LINE Messaging API | **v2** |

**3.2 Data flow**

1. User pastes full LINE message text into Gradio text area
2. **Message sanitizer** strips prompt injection patterns from raw input (before any other processing)
3. **URL extractor** parses URLs from message text.
4. **Message signal analyzer** runs on the message text (excluding URLs):
   - Urgency keywords: 限時, 馬上, 立即, 今天到期, 緊急, 馬上處理
   - Gift / prize bait: 免費, 中獎, 獲得, 贈品, 禮品, 恭喜
   - Threat language: 帳號停用, 法院傳票, 警察, 違規, 凍結
   - Impersonation hints: bank names (土地銀行, 玉山銀行…), government agencies (健保署, 警政署…), couriers (黑貓, 7-11, 全家…)

**Branch A — URL found:**

5. **URL validator** runs synchronously — blocks private IPs, localhost, non-http schemes, cloud metadata endpoints (~0ms)
6. **URL unshortener** resolves redirects (lin.ee, bit.ly). Max 3 hops.
7. These two run in parallel via `ThreadPoolExecutor`:
   - **Web scraper** fetches page (5s connect timeout, 10s read, 2MB cap, subprocess isolated)
   - **Domain enricher** runs WHOIS lookup + domain age + typosquat analysis (cached 24h)
8. **Content sanitizer** strips HTML to visible text only. Caps at 3000 tokens.
9. **RAG retriever** runs hybrid search using BOTH message text and page content as query. Returns top-3 KB pattern documents.
10. **Prompt builder** assembles: system prompt + message signals + WHOIS data + page content + retrieved KB patterns

**Branch B — No URL found:**

5. **RAG retriever** runs hybrid search using message text only as query. Returns top-3 KB pattern documents.
6. **Prompt builder** assembles: system prompt + message signals + retrieved KB patterns (no URL/page content)
7. LLM is informed that no URL was present — verdict may be `suspicious` at most unless message wording alone is highly indicative.

**Both branches continue:**

11. **LLM** produces structured JSON output (enforced via JSON mode / tool use)
12. **Output formatter** validates schema with Pydantic, renders verdict card + plain summary in Gradio

**3.3 Output schema**

The LLM is forced to return valid JSON matching this Pydantic schema on every call:

```python
class FraudVerdict(BaseModel):
    verdict: Literal['fraud', 'suspicious', 'safe']
    confidence: float              # 0.0 – 1.0
    matched_patterns: list[str]    # KB pattern IDs
    message_signals: list[str]     # signals from message wording (urgency, impersonation, etc.)
    url_signals: list[str]         # signals from URL, WHOIS, page content
    plain_summary: str             # simple Traditional Chinese for elderly users
    domain_age_days: int | None
```

---

**4. Security design**

The app now has two attack surfaces: (1) raw text pasted by users (prompt injection via message content), and (2) arbitrary URLs fetched on their behalf (SSRF). Five defense layers in v1, sixth deferred.

| **Layer** | **Threat blocked** | **Implementation** | **Cost** |
|---|---|---|---|
| **Layer 0** | Prompt injection from pasted message | Strip/escape control characters and LLM instruction patterns from raw message input before processing | ~0ms |
| **Layer 1** | SSRF — private IP / internal endpoint access | Block private IP ranges (10.x, 192.168.x, 172.16.x, 127.x), localhost, AWS/GCP metadata endpoints (169.254.169.254), non-http schemes | ~0ms |
| **Layer 2** | Redirect abuse, timeout/hang, oversized responses | httpx in subprocess. 5s connect timeout, 10s read timeout, 2MB response cap, max 3 redirects. Subprocess hard-killed by OS after 15s. | ~0ms overhead |
| **Layer 3** | Prompt injection via hidden HTML content | Strip all tags, extract visible text only via BeautifulSoup. Cap at 3000 tokens. Hidden comments and invisible divs never reach the LLM. | ~0ms |
| **Layer 4** | Redirect to private IP after DNS resolution | Resolve hostname to IP before fetching. Re-check resolved IP against private ranges (DNS rebinding defense). | ~50ms |
| **Layer 5 (v2)** | Scraper crash affects main app | Run scraper in dedicated Docker container per request. Adds 2–5s cold start. Deferred — subprocess isolation sufficient for MVP scale. | 2–5s |

---

**5. Knowledge base**

**5.1 Structure**

Each pattern is a markdown file in `/knowledge_base/`. Filename = pattern ID. Both BM25 and ChromaDB index from the same files on startup.

```
knowledge_base/
  tw_fake_bank_login.md
  tw_line_gift_card.md
  tw_investment_scam.md
  tw_fake_delivery.md
  tw_installment_cancellation.md
  tw_romance_scam.md
  tw_lottery_prize.md
  tw_government_impersonation.md
  ...
```

**5.2 Pattern document format**

```markdown
# Pattern ID: tw_line_gift_card
## Name: LINE gift card scam (線上禮品卡詐騙)
## Category: messaging_platform_scam
## Risk level: high
## Description
Scammer hijacks a victim's LINE account and messages their contacts asking them to buy
convenience store gift cards (7-Eleven, FamilyMart) and send photos of the redemption codes.
## Red flag signals
- Urgent request to buy gift cards from a "friend"
- Request made via LINE message
- Asks for card codes or photos of the card back
- Sender cannot video call or seems evasive
## Example message wording (話術)
「我現在有急事，能不能幫我買一張7-11的禮品卡？我等一下還你錢」
## Keywords (zh-TW)
禮券, 禮品卡, 7-11, 全家, 遊戲點數, 儲值卡
## Common URLs / domains
(none — this scam typically does not require a URL click)
## Source
165.gov.tw case report, scraped 2026-04-15
```

**5.3 Taiwan scam categories to cover (v1)**

- `tw_fake_bank_login` — phishing pages impersonating Taiwan banks (土地銀行, 台灣銀行, 玉山銀行)
- `tw_line_gift_card` — LINE account hijack + gift card request
- `tw_investment_scam` — fake high-return investment platforms (假投資詐騙)
- `tw_fake_delivery` — fake 黑貓/7-11 delivery fee pages
- `tw_installment_cancellation` — fake bank calls about accidental installment plans (解除分期付款)
- `tw_romance_scam` — long-game relationship scams that eventually ask for money
- `tw_lottery_prize` — you won a prize, pay a small processing fee
- `tw_government_impersonation` — fake NHI / police / court notifications

Target: 20–30 pattern documents for v1.

**5.4 KB data sources (semi-automated scraping)**

| **Source** | **Type** | **What to collect** | **Script** |
|---|---|---|---|
| 165.npa.gov.tw | Official anti-fraud | Fraud pattern descriptions, case reports, 話術 examples | `scrapers/scrape_165.py` |
| PTT (ptt.cc — Gossiping, fraud-adjacent boards) | Community | Real fraud messages shared by victims | `scrapers/scrape_ptt.py` |
| CNA / UDN / LTN news sites | News media | Articles quoting verbatim fraud messages | `scrapers/scrape_news.py` |
| TWCERT/CC (twcert.org.tw) | Technical | Phishing domain alerts and message examples | `scrapers/scrape_twcert.py` |

**Scraping workflow:**

1. Run scraper scripts → raw dumps saved in `scrapers/raw/`
2. Human review: flag relevant passages, discard noise, validate labels
3. `scrapers/build_kb.py` formats reviewed content into KB markdown files
4. Commit KB files to git for version tracking

---

**6. Tech stack**

| **Component** | **Choice** | **Rationale** |
|---|---|---|
| **UI** | Gradio | Zero frontend code. Free public link via Hugging Face Spaces. Supports Chinese text input. |
| **URL extractor** | Python regex + urllib | Handles mangled URLs, bare domains, lin.ee/bit.ly formats common in LINE messages. |
| **Message analyzer** | regex + zh-TW keyword lists | Fast, no model needed for keyword signals. Lists curated from 165.gov.tw patterns. |
| **Web scraper** | httpx + BeautifulSoup | Async-capable, handles redirects, lightweight. subprocess wrapper for isolation. |
| **Domain enricher** | python-whois | WHOIS lookup in pure Python. Cache results 24h. |
| **Keyword search** | rank_bm25 | BM25 in pure Python, zero infra, indexes on startup from markdown files. |
| **Vector store** | ChromaDB (in-memory) | No server needed for MVP. Persists to local file. Upgrade to hosted Chroma or Pinecone in v2. |
| **Embeddings** | text-embedding-3-small | OpenAI. Multilingual, cheap (~$0.02/1M tokens). Handles zh-TW well. |
| **LLM** | Claude Sonnet 4.6 | Strong structured output. JSON mode enforced. |
| **Output schema** | Pydantic v2 | Validates LLM JSON output. Hard fails if schema violated — no silent garbage. |
| **Deployment** | Hugging Face Spaces | Free, public URL, git-based deploy. Sufficient for <10 users. |
| **Eval** | Python + pandas + CSV | Simple eval loop. No MLflow needed at this scale. |
| **KB format** | Markdown files in /knowledge_base/ | Human-editable, git-tracked, no DB migration when adding patterns. |

---

**7. Evaluation**

**7.1 Test set structure**

Labeled dataset of ~100 real LINE messages stored in `eval/labeled_messages.csv`:

```
message_text, label, url_present, source, notes
"您的帳號異常，請立即點擊以下連結確認...", fraud, true, 165.gov.tw, fake bank login
"7-11取貨通知，請於24小時內完成付款...", fraud, true, ptt_scrape, fake delivery
```

Only messages with `url_present=true` are included in the eval set.

**7.2 Metrics**

```
Precision = TP / (TP + FP)   # of flagged-fraud messages, how many actually are fraud
Recall    = TP / (TP + FN)   # of actual fraud messages, how many did we catch
F1        = 2 * P * R / (P + R)
```

**Optimization target: maximize recall.** Missing a fraud (FN) causes real harm to elderly users; a false alarm (FP) is annoying but safe.

Additional dimensions tracked:
- Performance by scam category (investment vs delivery vs bank phishing)
- URL-only signal vs message wording signal vs combined (ablation)
- Confidence calibration (does confidence ≥ 0.9 actually correlate with high fraud rate?)

**7.3 Fraud message collection strategy**

| **Source** | **Expected yield** | **Label quality** |
|---|---|---|
| 165.gov.tw case reports | 30–50 messages | High (official) |
| PTT / community posts | 20–30 messages | Medium (community, needs verification) |
| News articles quoting fraud messages | 20–30 messages | High (editorial review) |
| Synthetic safe messages | 30–40 messages | High (hand-crafted) |

---

**8. Open questions**

**[ ]** How to handle JavaScript-heavy pages (SPAs) where httpx returns empty content? Options: Playwright headless browser (heavier), or skip with a clear error message.

**[ ]** What is the confidence threshold for 'suspicious' vs 'fraud' vs 'safe'? Needs calibration against eval set.

**[ ]** WHOIS lookup sometimes returns no data for .tw domains. Fallback strategy needed.

**[ ]** For messages containing multiple URLs, analyze all URLs or just the first?

**[ ]** How to handle URL-encoding and LINE-specific URL mangling in forwarded messages?

---

**9. Decisions log**

**Input: full LINE message (not URL only):**
Elderly users can forward entire messages via LINE's share function. The surrounding message wording is a strong fraud signal independent of the URL. URL-only input forces users to manually extract the URL, which is difficult for elderly users.

**Verdict issued for no-URL messages:**
Text-only fraud messages (impersonation, urgency, gift bait with no link) are still meaningful fraud signals. The system analyzes message wording and returns a verdict — capped at `suspicious` unless wording alone is highly indicative. This covers social engineering scripts that don't require a click, and matches the real-world use case where elderly users forward any suspicious message regardless of whether it contains a link.

**KB: semi-automated scraping (not fully manual):**
165.gov.tw, PTT, and news sources have rich publicly available fraud data. Semi-automated scraping with human review produces a higher-quality, larger KB faster than purely manual curation, while keeping a human in the loop.

**KB: markdown files (not a DB):**
Human-editable, git-tracked, zero migration cost when adding patterns.

**Retriever: hybrid BM25 + semantic, dual query:**
BM25 catches exact zh-TW scam terminology; semantic catches paraphrases. Both message text and page content are used as the retrieval query to cover cases where signals come from different sources.

**Security: new Layer 0 (message sanitizer):**
The input is now free-form text, not a URL. A user could paste a prompt injection attack disguised as a LINE message. Message must be sanitized before any LLM-adjacent processing.

**Eval: precision + recall on labeled messages:**
F1 metric tracked. Recall prioritized over precision — missing a fraud causes real harm to elderly users.

**Deployment: Hugging Face Spaces:**
Free, public URL, no infra ops. Upgrade to Railway or Fly.io if scale demands it.

**Output: Pydantic-validated JSON:**
Prevents silent schema violations. Fail loudly if LLM returns unexpected format.

**Domain enricher: parallel with scraper:**
WHOIS ~1s, scrape ~5–8s. Running concurrently saves wall-clock time at zero cost.

---

**10. Iteration history**

| **Version** | **Date** | **Changes** |
|---|---|---|
| v0.1 | 4/7/2026 | Initial design. Problem statement, MVP scope, URL-only input, 6-layer architecture, security model (layers 1–4), KB structure, tech stack, open questions, decisions log. |
| v0.2 | 4/15/2026 | Scope update: input changed from URL-only to full LINE message text. Added URL extractor, message signal analyzer, message sanitizer (Layer 0). KB shifted to semi-automated scraping from 165.gov.tw, PTT, news (new scrapers/ directory). Eval changed from labeled URLs to labeled messages with precision/recall. Output schema updated with `message_signals` + `url_signals`. Architecture updated to 8-layer data flow. |
| v0.3 | 4/15/2026 | Scope update: system now analyzes messages with or without a URL. No-URL messages are assessed on message wording alone (text-only fraud signals), with verdict capped at `suspicious` unless wording is highly indicative. Data flow updated to branch on URL presence. Decisions log updated. |
