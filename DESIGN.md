**Taiwan Fraud Detector**

System Design Document

Status: v0.4 — Phase 3 complete (RAG + KB + security hardening)

Last updated: Mon Apr 27 2026

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

**Implementation phases**

These phases keep the full RAG design in the roadmap while allowing an MVP to ship earlier.

- **Phase 1 — Minimal safe MVP**
  - Implement full LINE message input and text-only fraud signal analysis.
  - Add URL extraction and basic validation (scheme + private IP / metadata block).
  - Provide a simple Gradio UI with verdict, confidence, and summary.
  - Keep the knowledge base and retrieval design documented, but do not require them for the first working prototype.

- **Phase 2 — Safe URL branch and heuristics**
  - Add URL unshortening and URL-origin signals without full page scraping.
  - Add URL-based heuristics and reputation-style checks (e.g. suspicious domain patterns, known bad TLDs, red-flag keywords in the raw URL or message).
  - Log link metadata and use it as part of the verdict, while keeping actual page fetch logic isolated.
  - Keep KB and retrieval logic as planned but deprioritized until Phase 3.

- **Phase 3 — RAG retrieval and KB integration**
  - Populate a small seed `knowledge_base/` with initial scam pattern markdown files.
  - Implement BM25 and semantic retrieval modules from the KB.
  - Wire retrieved patterns into prompt assembly and use them as supporting evidence for the LLM verdict.
  - Add optional page content ingestion only if URL fetcher is hardened and isolated.

- **Phase 4 — Production hardening and isolation**
  - Move production hosting off the developer laptop into a cloud container or VM.
  - Run URL fetch/unshorten/scraping in a separate isolated process, container, or worker.
  - Add stronger network controls, egress policy, and safe fallback behavior for malicious or failed URLs.
  - Keep the full design and KB/retrieval architecture intact, but ensure the system is hardened before public exposure.

**Note:** The KB and retrieval architecture remain part of the long-term design, but they are not blockers for Phase 1. This lets the project ship a safe MVP first and grow toward the full RAG-enabled system.

### Phase 1 — Module boundaries and data flow

The first phase is intentionally narrow and focused on safe core functionality. It uses a small set of orthogonal modules so the flow is easy to implement and validate.

**Module boundaries**

- `app.py`
  - Orchestrates Phase 1 processing.
  - Accepts raw LINE message text from the UI.
  - Calls pipeline modules in order and renders the verdict.
- `pipeline/sanitizer.py`
  - Cleans raw message text.
  - Removes control characters, extra whitespace, and prompt-injection patterns.
  - Preserves readable zh-TW text for downstream analysis.
- `pipeline/extractor.py`
  - Extracts a candidate URL from free-form message text.
  - Normalizes common URL forms and prepares them for validation.
- `pipeline/validator.py`
  - Checks URL scheme and host information.
  - Blocks private/internal IP ranges, localhost, and cloud metadata addresses.
  - Rejects malformed or unsupported URLs without making any network calls.
- `pipeline/signal_analyzer.py`
  - Extracts fraud-related signals from the sanitized message text.
  - Uses rule-based keyword patterns for urgency, impersonation, prize/gift bait, and threats.

**Phase 1 data flow**

1. Raw LINE message text is entered in the UI.
2. `app.py` calls `sanitize_message()`.
3. The sanitized text is passed to `extract_url()`.
4. If a URL is found, `validate_url()` verifies it before any network activity.
5. `analyze_message_signals()` inspects the text for fraud signals.
6. `app.py` combines the results into a simple verdict, confidence score, and plain Chinese summary.

**All pipeline modules are now implemented** (Phase 2–3):

- `pipeline/retriever.py` — BM25 + semantic hybrid search, KB loader
- `pipeline/prompt_builder.py` — assembles message signals + URL metadata + KB evidence
- `pipeline/output.py` — Pydantic v2 `FraudVerdict` schema
- `pipeline/scraper.py` — subprocess-isolated page fetcher
- `pipeline/enricher.py` — WHOIS with 24 h in-memory cache
- `pipeline/unshortener.py` — shortener resolver with per-hop SSRF check
- `pipeline/url_metadata.py` — URL metadata extraction
- `pipeline/llm.py` — Claude Sonnet 4.6 via forced tool use

### Phase 1 — Implementation steps

1. Define the minimum module boundaries and data flow for Phase 1.
2. Implement basic message sanitizer:
   - remove control characters, extra whitespace, and malicious prompt injection patterns
   - preserve readable Chinese text for analysis and summary
3. Implement URL extraction:
   - detect `http://`, `https://`, and common bare/broken URL forms
   - normalize extracted URLs for validation
4. Implement URL validation:
   - block non-HTTP(S) schemes
   - block private IP ranges, localhost, and cloud metadata addresses
   - reject unsupported or malformed URLs before any network call
5. Implement text-only fraud signal analysis:
   - urgency, impersonation, prize/gift, threat keywords
   - simple rule-based signal collection for short LINE messages
6. Build a minimal Gradio UI in `app.py`:
   - one text input for the full LINE message
   - a submit button
   - verdict, confidence, and plain Chinese summary output
7. Add local tests and sample cases:
   - example safe and scam messages
   - cases with malformed or malicious URLs
   - verify the app returns safe responses without making network calls on invalid URLs

### Phase 1 progress tracker

- [x] Define Phase 1 module scope and interfaces
- [x] Implement `pipeline/sanitizer.py`
- [x] Implement `pipeline/extractor.py`
- [x] Implement `pipeline/validator.py`
- [x] Implement `pipeline/signal_analyzer.py` (or equivalent)
- [x] Implement `app.py` with Gradio UI
- [x] Add local test examples and run manual validation
- [x] Confirm Phase 1 end-to-end flow works locally

### Phase 2 — Implementation steps

1. Add URL branch heuristics without making unsafe live page fetches by default.
   - Implement URL unshortening for common redirect services such as `lin.ee`, `bit.ly`, and `tinyurl.com`.
   - Resolve redirects safely using a hardened HTTP client with strict timeouts, max redirects, and response size limits.
2. Extend URL-based analysis signals.
   - Detect suspicious domain patterns, known bad TLDs, IDN homograph lookalikes, and credential leaks in raw URLs.
   - Add reputation-style heuristics for URLs and domains, such as expired domains, newly created domains, and mismatched brand keywords.
3. Add safe URL metadata logging.
   - Capture URL origin metadata such as normalized domain, final destination, redirect chain length, and whether the URL contains credentials.
   - Keep this metadata isolated from any page scraping logic and ensure it is only used for verdict signals.
4. Integrate URL signals into the verdict.
   - Combine message signals and URL-origin signals into a richer verdict explanation.
   - Ensure the UI still returns a safe plain-language summary and confidence score.
5. Add Phase 2 local tests.
   - Create unit tests for URL unshortening, redirect handling, and URL-origin heuristics.
   - Add integration tests for the URL branch with both benign and suspicious redirect chains.
   - Keep Phase 2 coverage in a dedicated module at `tests/test_phase2.py`.
6. Update documentation and roadmap tracking.
   - Document Phase 2 progress in `DESIGN.md` and `README.md`.
   - Keep the KB and full RAG retrieval design in the roadmap but deprioritize until Phase 3.

**Phase 2 status:**
- Phase 2 URL branch features are implemented in the current codebase.
- Completed work includes safe shortener resolution, suspicious URL heuristics, metadata extraction, verdict integration, and dedicated Phase 2 tests.

### Phase 2 progress tracker

- [x] Design URL branch heuristics and safe unshortening flow
- [x] Implement URL unshortening and redirect chain analysis
- [x] Add URL-origin signal detection and reputation heuristics
- [x] Log URL metadata safely for verdict reasoning
- [x] Integrate URL signals into the Phase 1 verdict pipeline
- [x] Add local tests for URL branch behavior
- [x] Update docs and roadmap to reflect Phase 2 status

### Phase 3 — Implementation steps

1. Seed the knowledge base.
   - Collect a small set of reviewed scam pattern documents in `knowledge_base/`.
   - Format each file as Markdown with a clear title, category, and example scam language.
2. Implement hybrid retrieval.
   - Add BM25 keyword search over the KB text.
   - Add semantic embeddings search for higher-level similarity.
   - Keep retrieval code isolated in `pipeline/retriever.py`.
3. Build prompt assembly.
   - Create `pipeline/prompt_builder.py` to combine system instructions, message signals, URL metadata, and retrieved KB evidence.
   - Use safe prompt templates and guardrails for structured output.
   - Wire the assembled prompt into the app flow so it can be inspected and used for future LLM inference.
4. Integrate the KB into the verdict flow.
   - Use retrieved KB patterns as supporting evidence for the LLM decision.
   - Ensure the LLM can still return the simple zh-TW summary and verdict schema.
5. Add optional content ingestion carefully.
   - Only add page content retrieval after URL fetching is hardened and isolated.
   - Keep the Page fetcher separate from the core app flow until production isolation is in place.
6. Add Phase 3 validation.
   - Write tests for KB retrieval, prompt assembly, and evidence-aware verdicts.
   - Add evaluation cases that exercise retrieved KB pattern matching.

### Phase 3 progress tracker

- [x] Seed initial knowledge base with Taiwan scam pattern documents
- [x] Implement BM25 retrieval over the KB
- [x] Implement semantic search over the KB
- [x] Add prompt builder to assemble signals and KB evidence
- [x] Wire prompt builder output into the app flow for inspection
- [x] Integrate retrieved KB evidence into the verdict flow
- [x] Add optional page content ingestion path under isolation
- [x] Add Phase 3 tests and evaluation cases

**Constraints**

- Expected users: <10 concurrent, MVP phase
- Knowledge base: semi-automated scraping from public sources, refreshed manually
- Deployment: Hugging Face Spaces (free tier), no dedicated infra
- Budget: minimal — free-tier APIs and open-source libraries where possible

**Deployment note:**
- The production service should not run on a personal laptop if it will fetch untrusted URLs. Use a separate cloud-hosted or isolated environment for the app and URL fetcher so any malicious payload is contained away from your local machine.

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
| **URL unshortener** | Resolve bit.ly / lin.ee redirects; per-hop SSRF check blocks redirect-to-private-IP | httpx manual redirect loop + ipaddress | **v1** |
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
8. **Content sanitizer** strips HTML to visible text only. Caps at 12,000 characters.
9. **RAG retriever** runs hybrid search using BOTH message text and page content as query. Returns top-3 KB pattern documents.
10. **Prompt builder** assembles: message signals + URL metadata + WHOIS data + page content + retrieved KB patterns (system instructions live in `llm.py` as the API `system` parameter)

**Branch B — No URL found:**

5. **RAG retriever** runs hybrid search using message text only as query. Returns top-3 KB pattern documents.
6. **Prompt builder** assembles: system prompt + message signals + retrieved KB patterns (no URL/page content)
7. LLM is informed that no URL was present — verdict may be `suspicious` at most unless message wording alone is highly indicative.

**Both branches continue:**

11. **LLM** produces structured output enforced via `tool_choice={"type":"tool","name":"submit_verdict"}` (forced tool use — Claude never returns free text)
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
| **Layer 2** | Redirect abuse, timeout/hang, oversized responses | httpx in subprocess. 5s connect timeout, 10s read timeout, 2MB response cap, max 3 redirects. Subprocess hard-killed by OS after 15s. URL unshortener uses `follow_redirects=False` and resolves each `Location` header through `_is_ssrf_target()` before following — prevents shortener-to-private-IP redirect attacks. | ~0ms overhead |
| **Layer 3** | Prompt injection via hidden HTML content | Strip all tags, extract visible text only via BeautifulSoup. Cap at 12,000 characters. Hidden comments and invisible divs never reach the LLM. | ~0ms |
| **Layer 4** | Redirect to private IP after DNS resolution | Resolve hostname to IP before fetching. Re-check resolved IP against private ranges (DNS rebinding defense). | ~50ms |
| **Layer 5 (v2)** | Scraper crash affects main app | Run scraper in dedicated Docker container or isolated cloud worker per request. Adds 2–5s cold start. Deferred — subprocess isolation sufficient for MVP scale. Production should use a hardened separate service, not a personal laptop. | 2–5s |

---

**4.1 Deployment and URL-fetch isolation**

For this app, untrusted URL fetching is the highest-risk operation. The design therefore recommends a split architecture:

- Host the public-facing app and message parser in one service.
- Host the URL unshortener / fetcher / scraper in a separate isolated environment, ideally a cloud VM, container, or serverless worker.
- Keep the production fetcher separate from any sensitive developer workstation and limit its network egress to HTTP/HTTPS only.
- If a URL is deemed high-risk by heuristics or reputation checks, avoid fetching it entirely and still return a conservative verdict.

This approach minimizes the risk that a malicious URL can directly attack your local laptop or the main application environment.

**5. Knowledge base**

**5.1 Structure**

Each pattern is a markdown file in `/knowledge_base/`. Filename = pattern ID. Both BM25 and ChromaDB index from the same files on startup.

```
knowledge_base/
  bank_phishing.md             # fake bank login / account verification
  delivery_scam.md             # fake 黑貓/7-11 delivery fee
  gift_card_scam.md            # LINE hijack + convenience store gift card
  government_impersonation.md  # fake NHI / police / court notifications
  installment_cancellation.md  # fake bank call to cancel installment at ATM
  investment_scam.md           # fake high-return investment platform
  lottery_prize.md             # you won a prize, pay a processing fee
  romance_scam.md              # relationship scam leading to money request
```

**5.2 Pattern document format**

```markdown
# <Title in English>

Category: <zh-TW category name>

Description:
<One paragraph describing the scam pattern.>

Common signals:
- <signal 1>
- <signal 2>
- ...

Example message:
> <verbatim example scam message in zh-TW>

Keywords:
- <zh-TW keyword 1>
- <zh-TW keyword 2>
- ...
```

Filename = pattern ID (e.g. `gift_card_scam.md` → ID `gift_card_scam`). The ID is what the LLM references in `matched_patterns`.

**5.3 Taiwan scam categories to cover (v1)**

- `bank_phishing` — phishing pages impersonating Taiwan banks (土地銀行, 台灣銀行, 玉山銀行)
- `gift_card_scam` — LINE account hijack + convenience store gift card request
- `investment_scam` — fake high-return investment platforms (假投資詐騙)
- `delivery_scam` — fake 黑貓/7-11 delivery fee pages
- `installment_cancellation` — fake bank calls about accidental installment plans (解除分期付款)
- `romance_scam` — long-game relationship scams that eventually ask for money
- `lottery_prize` — you won a prize, pay a small processing fee
- `government_impersonation` — fake NHI / police / court notifications

All 8 categories are seeded. Target for v2: 20–30 documents with more variant examples per category.

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
| **Vector store** | ChromaDB (in-memory) | No server needed for MVP. Used only when `VOYAGE_API_KEY` is set; falls back to BM25-only otherwise. Upgrade to hosted Chroma or Pinecone in v2. |
| **Embeddings** | voyage-multilingual-2 (Voyage AI) | Anthropic-recommended embeddings. Strong zh-TW support. Requires `VOYAGE_API_KEY`. Falls back to BM25-only if key absent. |
| **LLM** | Claude Sonnet 4.6 (`claude-sonnet-4-6`) | Structured output enforced via `tool_choice` forced tool use — never returns free text. |
| **Output schema** | Pydantic v2 | Validates LLM JSON output. Hard fails if schema violated — no silent garbage. |
| **Deployment** | Hugging Face Spaces | Free, public URL, git-based deploy. Sufficient for <10 users. |
| **Eval** | Python + pandas + CSV | Simple eval loop. No MLflow needed at this scale. |
| **KB format** | Markdown files in /knowledge_base/ | Human-editable, git-tracked, no DB migration when adding patterns. |

---

**7. Evaluation**

**7.1 Test set structure**

Labeled dataset stored in `eval/labeled_messages.csv`. Current seed set: 25 messages (15 fraud across 8 categories, 8 safe, 2 suspicious). Run via `eval/eval.py`; use `--skip-fetch` to skip live URL resolution.

```
message_text, label, scam_category, verdict, confidence, matched_patterns, summary, tp, fp, fn, tn
"您的帳號異常，請立即點擊以下連結確認...", fraud, fake_bank_login, ...
"7-11取貨通知，請於24小時內完成付款...", fraud, fake_delivery, ...
```

Both URL and no-URL messages are included. Target for v2: expand to ~100 labeled messages.

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
| v0.4 | 4/27/2026 | Phase 3 complete. All 8 KB documents seeded (bank_phishing, delivery_scam, gift_card_scam, government_impersonation, investment_scam, installment_cancellation, lottery_prize, romance_scam). Subprocess-isolated scraper and 24 h-cached WHOIS enricher added. Hybrid BM25 + semantic retrieval wired into prompt builder and verdict flow. `FraudVerdict` output enforced via Claude tool_choice. SSRF gap in URL unshortener fixed: manual per-hop redirect following with `_is_ssrf_target()` check before each hop. `load_dotenv()` added at startup. KB loaded once at module import (`_KB_DOCS`). `analyze_line_message` return type changed from bare 8-tuple to `LineAnalysisResult` (NamedTuple). `SYSTEM_PROMPT` removed from `prompt_builder.py` — lives only in `llm.py` as the API `system` parameter. Eval harness added (`eval/eval.py`, 25-message seed set). 96 unit tests passing. |
