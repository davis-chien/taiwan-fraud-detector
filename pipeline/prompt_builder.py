from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def _format_list(label: str, items: Sequence[str]) -> str:
    if not items:
        return f"{label}: 無"
    return f"{label}: {', '.join(items)}"


def _format_metadata(metadata: Dict[str, Any]) -> str:
    fields = [
        f"原始網址: {metadata.get('original_url', '')}",
        f"最終網址: {metadata.get('final_url', '')}",
        f"跳轉次數: {metadata.get('redirect_hops', 0)}",
        f"主機名稱: {metadata.get('hostname', '')}",
        f"路徑: {metadata.get('path', '')}",
        f"查詢: {metadata.get('query', '')}",
        f"是否含憑證: {metadata.get('has_credentials', False)}",
    ]
    return "\n".join(fields)


def _format_retrieved_docs(docs: Sequence[Dict[str, Any]]) -> str:
    if not docs:
        return "知識庫檢索結果: 無"

    formatted: List[str] = ["知識庫檢索結果 (請在 matched_patterns 欄位引用相符的文件 ID):"]
    for index, item in enumerate(docs, start=1):
        doc = item["doc"]
        score = item.get("score", 0.0)
        content = doc.get("content", "").strip().replace("\n", " ")
        if len(content) > 200:
            content = content[:200].rstrip() + "..."
        formatted.append(
            f"{index}. 文件 ID: [{doc.get('id', 'unknown')}] — {doc.get('title', 'unknown')} (score={score:.3f})\n"
            f"   {content}"
        )
    return "\n".join(formatted)


def _format_domain_info(domain_info: Dict[str, Any]) -> str:
    parts: List[str] = []
    age = domain_info.get("domain_age_days")
    if age is not None:
        parts.append(f"域名年齡: {age} 天")
        if age < 30:
            parts.append("（警告：此域名在30天內剛創建，為常見詐騙特徵）")
    registrar = domain_info.get("registrar")
    if registrar:
        parts.append(f"域名註冊商: {registrar}")
    return "\n".join(parts)


def build_prompt(
    message: str,
    message_signals: Sequence[str],
    url: str,
    url_status: str,
    url_signals: Sequence[str],
    url_metadata: Dict[str, Any],
    retrieved_docs: Sequence[Dict[str, Any]],
    page_content: str = "",
    domain_info: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a prompt combining message context, URL signals, page content, and KB evidence."""
    prompt_parts: List[str] = []

    prompt_parts.append("---")
    prompt_parts.append("使用者 LINE 訊息:")
    prompt_parts.append(message)
    prompt_parts.append(_format_list("訊息信號", list(message_signals)))
    prompt_parts.append("---")
    prompt_parts.append("網址資訊:")
    prompt_parts.append(f"檢測到網址: {url or '無'}")
    prompt_parts.append(f"網址驗證狀態: {url_status}")
    prompt_parts.append(_format_list("網址特徵", list(url_signals)))
    prompt_parts.append(_format_metadata(url_metadata or {}))

    domain_info_text = _format_domain_info(domain_info or {})
    if domain_info_text:
        prompt_parts.append("---")
        prompt_parts.append("域名資訊:")
        prompt_parts.append(domain_info_text)

    if page_content:
        prompt_parts.append("---")
        prompt_parts.append("頁面內容 (節錄):")
        prompt_parts.append(page_content)

    prompt_parts.append("---")
    prompt_parts.append(_format_retrieved_docs(retrieved_docs))
    prompt_parts.append("---")
    prompt_parts.append(
        "請根據上述資訊判斷訊息是否可疑或詐騙，"
        "在 matched_patterns 欄位中填入你實際引用的知識庫文件 ID，"
        "並在 plain_summary 欄位輸出簡短繁體中文說明。"
    )

    return "\n".join(prompt_parts)
