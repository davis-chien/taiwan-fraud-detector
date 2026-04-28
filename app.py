import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, NamedTuple, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

from pipeline import (
    analyze_message_signals,
    analyze_url_signals,
    build_prompt,
    bm25_search,
    extract_url,
    extract_url_metadata,
    hybrid_search,
    infer_llm_prompt,
    load_kb_documents,
    sanitize_message,
    sanitize_page_content,
    validate_url,
)
from pipeline.fetcher_client import fetch_page, get_domain_info, unshorten_url
from pipeline.output import FraudVerdict

_KB_DOCS: List[Dict[str, Any]] = load_kb_documents("knowledge_base")


class LineAnalysisResult(NamedTuple):
    verdict: str
    confidence: float
    plain_summary: str
    url: str
    url_status: str
    url_metadata: str
    prompt_text: str
    matched_patterns: str


def build_verdict(
    message: str,
    url: Optional[str],
    url_status: Optional[str],
    url_signals: Optional[List[str]] = None,
    url_metadata: Optional[Dict[str, Any]] = None,
    message_signals: Optional[List[str]] = None,
) -> FraudVerdict:
    """Rule-based fallback verdict used when LLM inference is unavailable."""
    signals = message_signals if message_signals is not None else (
        analyze_message_signals(message) if message else []
    )
    url_sigs = url_signals or []

    if url is not None and url_status != "ok":
        return FraudVerdict(
            verdict="suspicious",
            confidence=0.65,
            matched_patterns=[],
            message_signals=signals,
            url_signals=url_sigs,
            plain_summary="此訊息包含的連結看起來不安全或無法驗證，請勿點擊。",
        )

    if url_sigs:
        return FraudVerdict(
            verdict="suspicious",
            confidence=0.8,
            matched_patterns=[],
            message_signals=signals,
            url_signals=url_sigs,
            plain_summary="這個連結包含可疑網址特徵，建議不要點擊並確認發送者身分。",
        )

    if signals:
        return FraudVerdict(
            verdict="suspicious",
            confidence=0.75,
            matched_patterns=[],
            message_signals=signals,
            url_signals=url_sigs,
            plain_summary="訊息內容包含常見詐騙話術，請小心驗證發件人身分，建議不要點擊任何連結。",
        )

    return FraudVerdict(
        verdict="safe",
        confidence=0.85,
        matched_patterns=[],
        message_signals=signals,
        url_signals=url_sigs,
        plain_summary="此訊息目前看起來沒有明顯詐騙特徵，但仍請保持謹慎。",
    )


def _retrieve_kb_docs(query: str, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not docs:
        return []

    if os.getenv("VOYAGE_API_KEY"):
        try:
            return hybrid_search(query, docs, top_n=3)
        except Exception:
            return bm25_search(query, docs, top_n=3)

    return bm25_search(query, docs, top_n=3)


def analyze_line_message(raw_message: str) -> LineAnalysisResult:
    sanitized = sanitize_message(raw_message)
    if not sanitized:
        return LineAnalysisResult(
            verdict="safe",
            confidence=0.0,
            plain_summary="請輸入 LINE 訊息內容。",
            url="",
            url_status="",
            url_metadata="",
            prompt_text="",
            matched_patterns="",
        )

    url = extract_url(sanitized)
    url_status = None
    url_signals: List[str] = []
    url_metadata: Optional[Dict[str, Any]] = None
    page_content = ""
    domain_info: Optional[Dict[str, Any]] = None

    if url:
        resolved_url, changed, redirect_status, redirect_chain = unshorten_url(url)
        url_metadata = extract_url_metadata(
            final_url=resolved_url,
            original_url=url,
            redirect_chain=redirect_chain,
        )
        url = resolved_url
        if redirect_status not in {"ok", "unchanged", "resolved"}:
            url_status = redirect_status
        else:
            url_status = "ok"

        valid, reason = validate_url(url)
        if not valid:
            prompt_text = build_prompt(
                message=sanitized,
                message_signals=analyze_message_signals(sanitized),
                url=url,
                url_status=url_status or "ok",
                url_signals=[],
                url_metadata=url_metadata or {},
                retrieved_docs=_retrieve_kb_docs(sanitized, _KB_DOCS),
            )
            return LineAnalysisResult(
                verdict="suspicious",
                confidence=0.65,
                plain_summary="這個連結被判斷為不安全或無法驗證，請勿點擊。",
                url=url,
                url_status=reason,
                url_metadata=json.dumps(url_metadata, ensure_ascii=False),
                prompt_text=prompt_text,
                matched_patterns="",
            )

        url_signals = analyze_url_signals(url)

        # Skip page fetch when the URL is already high-risk by heuristics.
        # IDN homograph is a strong deception signal on its own; 3+ independent
        # signals give enough evidence for a verdict without fetching the page.
        hostname = urlparse(url).hostname or ""
        _high_risk = "idn_homograph" in url_signals or len(url_signals) >= 3

        if not _high_risk:
            # Fetch page content and WHOIS in parallel.
            with ThreadPoolExecutor(max_workers=2) as executor:
                scrape_future = executor.submit(fetch_page, url)
                enrich_future = executor.submit(get_domain_info, hostname)

            try:
                page_result = scrape_future.result(timeout=20)
                if page_result.get("error") == "fetcher_unavailable":
                    url_signals = url_signals + ["fetcher_unavailable"]
                else:
                    page_content = sanitize_page_content(page_result.get("text", ""))
            except Exception:
                page_content = ""

            try:
                domain_info = enrich_future.result(timeout=15)
            except Exception:
                domain_info = None
        else:
            # High-risk URL: skip page fetch, still collect WHOIS for domain age.
            try:
                domain_info = get_domain_info(hostname)
            except Exception:
                domain_info = None

    msg_signals = analyze_message_signals(sanitized)
    kb_docs = _KB_DOCS

    # Use message + page content as combined RAG query when page was fetched.
    rag_query = sanitized
    if page_content:
        rag_query = f"{sanitized} {page_content[:500]}"

    retrieved_docs = _retrieve_kb_docs(rag_query, kb_docs)

    prompt_text = build_prompt(
        message=sanitized,
        message_signals=msg_signals,
        url=url or "",
        url_status=url_status or "ok",
        url_signals=url_signals,
        url_metadata=url_metadata or {},
        retrieved_docs=retrieved_docs,
        page_content=page_content,
        domain_info=domain_info,
    )

    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            fraud_verdict = infer_llm_prompt(prompt_text)
        except Exception:
            fraud_verdict = build_verdict(
                sanitized, url, url_status, url_signals, url_metadata, msg_signals
            )
    else:
        fraud_verdict = build_verdict(
            sanitized, url, url_status, url_signals, url_metadata, msg_signals
        )

    # Fill domain_age_days from WHOIS if the LLM left it unset.
    if fraud_verdict.domain_age_days is None and domain_info:
        age = domain_info.get("domain_age_days")
        if age is not None:
            fraud_verdict = fraud_verdict.model_copy(update={"domain_age_days": age})

    return LineAnalysisResult(
        verdict=fraud_verdict.verdict,
        confidence=fraud_verdict.confidence,
        plain_summary=fraud_verdict.plain_summary,
        url=url or "",
        url_status=url_status or "ok",
        url_metadata=json.dumps(url_metadata, ensure_ascii=False) if url_metadata else "",
        prompt_text=prompt_text,
        matched_patterns=", ".join(fraud_verdict.matched_patterns),
    )


def launch_ui() -> None:
    import gradio as gr

    with gr.Blocks() as demo:
        gr.Markdown("# Taiwan Fraud Detector — Phase 3")
        input_box = gr.TextArea(
            label="請貼上完整 LINE 訊息內容",
            placeholder="例如：您好，您已中獎，請點擊 https://example.com 進行確認",
            lines=6,
        )
        output_verdict = gr.Textbox(label="判斷結果")
        output_confidence = gr.Textbox(label="信心分數")
        output_summary = gr.Textbox(label="簡短摘要")
        output_matched_patterns = gr.Textbox(label="相符知識庫模式")
        output_url = gr.Textbox(label="解析到的 URL")
        output_url_status = gr.Textbox(label="URL 驗證狀態")
        output_url_metadata = gr.Textbox(label="URL metadata")
        output_prompt = gr.Textbox(label="組合提示詞", lines=12)

        outputs = [
            output_verdict,
            output_confidence,
            output_summary,
            output_url,
            output_url_status,
            output_url_metadata,
            output_prompt,
            output_matched_patterns,
        ]

        input_box.submit(analyze_line_message, inputs=[input_box], outputs=outputs)
        gr.Button("分析訊息").click(analyze_line_message, inputs=[input_box], outputs=outputs)

    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", 7860)))


if __name__ == "__main__":
    launch_ui()
