**Taiwan Fraud Detector**

System Design Document

Status: v0.5 — Phase 4 code complete (containerization, fetcher isolation, egress policy, safe fallback). HF Spaces deployment pending. Phase 5 planned: eval expansion, KB expansion, ablation study, LLM/embeddings model comparison, confidence calibration.

Last updated: Tue Apr 28 2026

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
| ✓ Security hardening (layers 0–5) | — Custom domain / paid hosting |
| ✓ Eval harness with precision/recall on labeled messages | |
| ✓ Containerized for Docker + HF Spaces (deployment pending) | |

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

- **Phase 5 — Evaluation, model comparison, and optimization**
  - Expand the eval dataset from 25 to ~100 labeled LINE messages to make precision/recall numbers statistically meaningful.
  - Expand the knowledge base beyond 8 seed documents, guided by eval gaps identified in step 1.
  - Run an ablation study measuring the marginal contribution of each pipeline component (message signals, URL signals, KB retrieval, page content).
  - Compare Claude Sonnet 4.6 against open-source zh-TW-capable LLMs (Qwen2.5, TAIDE-LX) on the labeled eval set.
  - Compare Voyage AI embeddings against open-source alternatives (BAAI/bge-m3, multilingual-e5-large) for retrieval quality.
  - Calibrate the confidence score against the eval set; apply Platt scaling if miscalibrated.

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

### Phase 4 — Implementation steps

1. Containerize the app and configure deployment to Hugging Face Spaces.
   - Write a `Dockerfile` (python:3.11-slim, non-root user, port 7860).
   - Write a `.dockerignore` excluding tests, scrapers, eval data, and secrets.
   - Update `demo.launch()` to bind on `0.0.0.0` and respect the `PORT` env var.
   - Add HF Spaces YAML frontmatter to `README.md` (`sdk: docker`, `app_port: 7860`).
   - Add Docker run instructions and HF Spaces deployment steps to `README.md`.
2. Isolate the URL fetcher into a separate container or worker.
   - Move `pipeline/scraper.py`, `pipeline/unshortener.py`, and `pipeline/enricher.py` into a dedicated worker service.
   - Expose the worker via an internal HTTP API; the main app calls it rather than spawning subprocesses.
   - Apply network egress policy to the worker: HTTP/HTTPS only, no access to internal metadata endpoints.
3. Add stronger egress controls and safe fallback behavior.
   - Configure the fetcher worker's network so it cannot reach cloud metadata endpoints (169.254.169.254) or private IP ranges at the network level.
   - If the worker fails, crashes, or times out, the main app falls back to a conservative verdict without crashing.
   - If a URL is flagged high-risk by heuristics, skip the fetch entirely and still return a verdict.

### Phase 4 progress tracker

- [x] Containerize app: Dockerfile, .dockerignore, 0.0.0.0 bind, HF Spaces frontmatter
- [ ] Deploy to Hugging Face Spaces and confirm live URL
- [x] Isolate URL fetcher into a separate worker service (fetcher/main.py, fetcher/Dockerfile, pipeline/fetcher_client.py, docker-compose.yml)
- [x] Apply network egress policy to the fetcher worker (fetcher/entrypoint.sh: iptables blocks metadata + private IPs; docker-compose.yml: cap_add NET_ADMIN; gosu privilege drop)
- [x] Add safe fallback when fetcher worker is unreachable (fetcher_client: sentinel returns instead of local fallback when FETCHER_URL set; app.py: fetcher_unavailable surfaced as url_signal; high-risk URL skip: idn_homograph or 3+ signals skips page fetch)

### Phase 5 — Implementation steps

1. Expand the eval dataset to ~100 labeled LINE messages.
   - Run existing scrapers (`scrape_165.py`, `scrape_ptt.py`, `scrape_news.py`) to collect raw candidates from 165.gov.tw, PTT, and news articles.
   - Human-review and label candidates: fraud / suspicious / safe, with scam category tag.
   - Target distribution: ~15 messages per fraud category, ~20 safe, ~10 suspicious edge cases.
   - Add to `eval/labeled_messages.csv` and re-run `eval/eval.py` to establish a baseline.

2. Expand the knowledge base guided by eval gaps.
   - Identify which fraud categories have the weakest eval verdict accuracy after step 1.
   - Add more KB documents for weak categories: additional phrasings, newer scam variants, edge-case examples.
   - Target: 20–30 documents total (up from 8 seed files). Re-run eval to confirm improvement.

3. Run an ablation study.
   - Evaluate the pipeline with components selectively disabled: message signals only, URL signals only, KB retrieval only (no page content), full pipeline.
   - Also compare BM25-only vs semantic-only vs hybrid retrieval.
   - Produce a results table showing the marginal contribution of each component to precision, recall, and F1.
   - Document findings in `eval/ablation_results.csv` and summarize in DESIGN.md.

4. LLM model comparison.
   - Evaluate two open-source zh-TW-capable alternatives against Claude Sonnet 4.6 on the expanded labeled set:
     - **Qwen2.5-72B** (Alibaba) — strong zh-TW benchmark performance, open weights.
     - **TAIDE-LX-7B-Chat** — Taiwan government-backed model, trained on Traditional Chinese corpus.
   - Key tradeoffs to document: structured output reliability (Claude forced tool use vs constrained decoding), zh-TW fluency in `plain_summary`, inference cost (API vs GPU hosting), verdict accuracy on the eval set.
   - Add a model comparison table to §6 Tech stack.

5. Embeddings model comparison.
   - Evaluate open-source embedding alternatives against Voyage AI `voyage-multilingual-2`:
     - **BAAI/bge-m3** — strong Chinese retrieval, self-hosted (~570MB), no API dependency.
     - **multilingual-e5-large** — broad multilingual coverage, lighter weight.
   - Measure retrieval quality (top-3 KB match accuracy) on the expanded eval set.
   - Key tradeoff: API cost and dependency (Voyage AI) vs self-hosted cold-start and memory (bge-m3).
   - Update ChromaDB configuration to support swappable embedding backends.

6. Confidence calibration.
   - Plot a reliability diagram: does LLM-reported confidence ≥ 0.9 actually correlate with fraud rate?
   - If miscalibrated, apply Platt scaling using the eval set labels.
   - Document calibration results and update `plain_summary` guidance if threshold adjustments are needed.

### Phase 5 progress tracker

- [x] Expand eval dataset to ~100 labeled messages via scrapers + human review (110 messages: 80 fraud across 8 categories, 20 safe, 10 suspicious; scrape_165.py added)
- [ ] Re-run eval harness to establish baseline precision/recall by category
- [ ] Expand KB to 20–30 documents guided by category-level eval gaps
- [ ] Run ablation study (message-only, URL-only, KB-only, BM25-only, semantic-only, full pipeline)
- [ ] LLM comparison: Qwen2.5-72B and TAIDE-LX-7B-Chat vs Claude Sonnet 4.6
- [ ] Embeddings comparison: bge-m3 and multilingual-e5-large vs voyage-multilingual-2
- [ ] Confidence calibration: reliability diagram + Platt scaling if needed

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
| **Semantic search** | Embedding similarity on fraud pattern KB | ChromaDB + voyage-multilingual-2 (Voyage AI) | **v1** |
| **Knowledge base** | Taiwan/LINE scam pattern documents | Markdown files in /knowledge_base/ | **v1** |
| **Prompt builder** | Assemble system + message signals + URL content + KB patterns | Python f-strings / Jinja2 | **v1** |
| **LLM reasoning** | Analyze and produce structured verdict | Claude Sonnet 4.6 | **v1** |
| **Output formatter** | Parse JSON, render verdict + summary | Pydantic v2 | **v1** |
| **Gradio UI** | Web interface, shareable link | Gradio on HF Spaces | **v1** |
| **Eval harness** | Measure precision/recall on labeled messages | Python + pandas + CSV | **v1** |
| **KB scraper** | Semi-automated scraping from 165.gov.tw, PTT, news | httpx + BeautifulSoup | **v1** |
| **Fetcher worker** | Isolated container for URL fetch / unshorten / WHOIS | FastAPI + uvicorn, port 8080 (internal only) | **v1** |
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
6. **URL unshortener** resolves redirects (lin.ee, bit.ly). Max 3 hops. Routed through fetcher worker when `FETCHER_URL` is set.
7. **URL signal analyzer** checks TLD, IDN homograph, suspicious keywords. If high-risk (idn_homograph or 3+ signals), skip page fetch and proceed to step 9 with WHOIS only.
8. These two run in parallel via `ThreadPoolExecutor` (skipped if high-risk URL):
   - **Web scraper** fetches page via fetcher worker HTTP API (falls back to subprocess when running locally). 5s connect, 10s read, 2MB cap.
   - **Domain enricher** runs WHOIS lookup + domain age via fetcher worker (cached 24h).
9. **Content sanitizer** strips HTML to visible text only. Caps at 12,000 characters.
10. **RAG retriever** runs hybrid search using BOTH message text and page content as query. Returns top-3 KB pattern documents.
11. **Prompt builder** assembles: message signals + URL metadata + WHOIS data + page content + retrieved KB patterns (system instructions live in `llm.py` as the API `system` parameter)

**Branch B — No URL found:**

5. **RAG retriever** runs hybrid search using message text only as query. Returns top-3 KB pattern documents.
6. **Prompt builder** assembles: system prompt + message signals + retrieved KB patterns (no URL/page content)
7. LLM is informed that no URL was present — verdict may be `suspicious` at most unless message wording alone is highly indicative.

**Both branches continue:**

12. **LLM** produces structured output enforced via `tool_choice={"type":"tool","name":"submit_verdict"}` (forced tool use — Claude never returns free text)
13. **Output formatter** validates schema with Pydantic, renders verdict card + plain summary in Gradio

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

The app has two attack surfaces: (1) raw text pasted by users (prompt injection via message content), and (2) arbitrary URLs fetched on their behalf (SSRF). Six defense layers implemented in v1.

| **Layer** | **Threat blocked** | **Implementation** | **Cost** |
|---|---|---|---|
| **Layer 0** | Prompt injection from pasted message | Strip/escape control characters and LLM instruction patterns from raw message input before processing | ~0ms |
| **Layer 1** | SSRF — private IP / internal endpoint access | Block private IP ranges (10.x, 192.168.x, 172.16.x, 127.x), localhost, AWS/GCP metadata endpoints (169.254.169.254), non-http schemes | ~0ms |
| **Layer 2** | Redirect abuse, timeout/hang, oversized responses | httpx in subprocess. 5s connect timeout, 10s read timeout, 2MB response cap, max 3 redirects. Subprocess hard-killed by OS after 15s. URL unshortener uses `follow_redirects=False` and resolves each `Location` header through `_is_ssrf_target()` before following — prevents shortener-to-private-IP redirect attacks. | ~0ms overhead |
| **Layer 3** | Prompt injection via hidden HTML content | Strip all tags, extract visible text only via BeautifulSoup. Cap at 12,000 characters. Hidden comments and invisible divs never reach the LLM. | ~0ms |
| **Layer 4** | Redirect to private IP after DNS resolution | Resolve hostname to IP before fetching. Re-check resolved IP against private ranges (DNS rebinding defense). | ~50ms |
| **Layer 5** | Scraper crash / exploit affects main app | `fetcher/` FastAPI worker runs in a separate container. iptables egress policy blocks cloud metadata endpoints + RFC 1918 private IPs; allows DNS/WHOIS/HTTP/HTTPS only. Main app calls worker via HTTP (`FETCHER_URL`); falls back to in-process when running without Docker Compose. Not available on HF Spaces (single-container). | ~0ms overhead |

---

**4.1 Deployment and URL-fetch isolation**

Untrusted URL fetching is the highest-risk operation. The system implements a split architecture:

- The Gradio app (`app.py`) handles message analysis, RAG retrieval, and LLM inference.
- The fetcher worker (`fetcher/main.py`) handles all untrusted network operations: URL unshortening, page fetching, and WHOIS. It runs in a separate container with an iptables egress policy that blocks cloud metadata endpoints and RFC 1918 private IPs, allowing only DNS/WHOIS/HTTP/HTTPS outbound.
- The main app communicates with the fetcher via HTTP (`FETCHER_URL=http://fetcher:8080`). If the worker is unreachable, it returns safe sentinel values and continues to produce a verdict from message and URL signals alone.
- URLs flagged as high-risk by heuristics (IDN homograph, or 3+ independent signals) skip the page fetch entirely. WHOIS is still collected for domain age.

When running without Docker Compose (e.g. HF Spaces single-container or local Python), URL fetch operations fall back to in-process subprocess calls. Layer 5 isolation is only active under Docker Compose.

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

Both URL and no-URL messages are included. **Phase 5 target: ~100 labeled messages** (~15 per fraud category, ~20 safe, ~10 suspicious edge cases) to make per-category precision/recall statistically meaningful.

**7.1.1 Ablation study structure (Phase 5)**

Eval harness will be extended to support component toggling for ablation runs. Results stored in `eval/ablation_results.csv`.

| Run | Components active | Purpose |
|---|---|---|
| message-only | message signals | Baseline: wording analysis alone |
| url-only | URL signals + heuristics | URL branch contribution without message context |
| kb-only (BM25) | BM25 retrieval + full pipeline | BM25 retrieval in isolation |
| kb-only (semantic) | semantic retrieval + full pipeline | Semantic retrieval in isolation |
| no-page-content | full pipeline, page fetch disabled | Value of fetching page vs signals-only |
| full | all components | End-to-end system |

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

**Phase 5 — LLM choice (Claude vs open-source zh-TW models):**
Claude Sonnet 4.6 offers reliable structured output via forced tool use and strong multilingual reasoning. Open-source alternatives (Qwen2.5-72B, TAIDE-LX-7B-Chat) eliminate per-call API cost and may perform better on Traditional Chinese `plain_summary` fluency, but require GPU hosting and depend on constrained decoding (e.g. outlines, lm-format-enforcer) for structured output — adding infrastructure complexity and a new failure mode. Phase 5 will measure verdict accuracy on the labeled eval set across all three to make this decision evidence-based rather than assumed.

**Phase 5 — Embeddings choice (Voyage AI vs open-source):**
Voyage AI `voyage-multilingual-2` is Anthropic-recommended, strong on zh-TW, and zero infrastructure overhead. BAAI/bge-m3 is the strongest open-source alternative for Chinese retrieval and eliminates the API dependency and per-token cost, but adds ~570MB model weight to the container and a self-hosted inference step. Phase 5 will compare retrieval quality (top-3 KB match accuracy on the eval set) to determine whether the dependency is justified by measurable quality gains.

**Phase 5 — KB expansion driven by eval gaps (not upfront):**
Adding KB documents without measuring which categories are weak risks expanding areas that already perform well. Eval expansion comes first; KB additions are then targeted at the weakest-performing fraud categories identified by the harness.

---

**10. Iteration history**

| **Version** | **Date** | **Changes** |
|---|---|---|
| v0.1 | 4/7/2026 | Initial design. Problem statement, MVP scope, URL-only input, 6-layer architecture, security model (layers 1–4), KB structure, tech stack, open questions, decisions log. |
| v0.2 | 4/15/2026 | Scope update: input changed from URL-only to full LINE message text. Added URL extractor, message signal analyzer, message sanitizer (Layer 0). KB shifted to semi-automated scraping from 165.gov.tw, PTT, news (new scrapers/ directory). Eval changed from labeled URLs to labeled messages with precision/recall. Output schema updated with `message_signals` + `url_signals`. Architecture updated to 8-layer data flow. |
| v0.3 | 4/15/2026 | Scope update: system now analyzes messages with or without a URL. No-URL messages are assessed on message wording alone (text-only fraud signals), with verdict capped at `suspicious` unless wording is highly indicative. Data flow updated to branch on URL presence. Decisions log updated. |
| v0.4 | 4/27/2026 | Phase 3 complete. All 8 KB documents seeded (bank_phishing, delivery_scam, gift_card_scam, government_impersonation, investment_scam, installment_cancellation, lottery_prize, romance_scam). Subprocess-isolated scraper and 24 h-cached WHOIS enricher added. Hybrid BM25 + semantic retrieval wired into prompt builder and verdict flow. `FraudVerdict` output enforced via Claude tool_choice. SSRF gap in URL unshortener fixed: manual per-hop redirect following with `_is_ssrf_target()` check before each hop. `load_dotenv()` added at startup. KB loaded once at module import (`_KB_DOCS`). `analyze_line_message` return type changed from bare 8-tuple to `LineAnalysisResult` (NamedTuple). `SYSTEM_PROMPT` removed from `prompt_builder.py` — lives only in `llm.py` as the API `system` parameter. Eval harness added (`eval/eval.py`, 25-message seed set). 96 unit tests passing. |
| v0.5 | 4/28/2026 | Phase 4 code complete. `Dockerfile` + `.dockerignore` for main app (python:3.11-slim, UID 1000, port 7860). `docker-compose.yml` orchestrates app + fetcher on internal bridge network. `fetcher/` FastAPI worker isolates unshorten/fetch/enrich; `fetcher/Dockerfile` installs iptables + gosu; `fetcher/entrypoint.sh` applies OUTPUT egress policy (blocks metadata + RFC 1918, allows DNS/WHOIS/HTTP/HTTPS) before dropping to appuser via gosu. `pipeline/fetcher_client.py` routes fetch ops to worker when `FETCHER_URL` set; returns safe sentinel (not in-process fallback) when worker configured but unreachable. `app.py`: high-risk URL skip (idn_homograph or 3+ signals skips page fetch); `fetcher_unavailable` surfaced as url_signal. HF Spaces Docker frontmatter added to `README.md`. HF Spaces deployment pending. |
