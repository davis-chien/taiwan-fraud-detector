from __future__ import annotations

import os

import anthropic

from .output import FraudVerdict

MODEL = os.getenv("EVAL_MODEL_OVERRIDE", "claude-sonnet-4-6")

SYSTEM_PROMPT = (
    "你是台灣金融詐騙分析輔助系統。\n"
    "根據使用者提供的 LINE 訊息、URL 資訊、網址元資料，以及知識庫檢索結果，"
    "判斷是否存在詐騙風險。\n"
    "在 matched_patterns 欄位中，列出你實際用於判斷的知識庫文件 ID"
    "（格式為文件名稱，例如 bank_phishing）。\n"
    "在 plain_summary 欄位中，以長者能理解的簡短傳統中文說明（不超過 60 字）。\n"
    "必須使用 submit_verdict 工具回傳結果，不要輸出其他文字。"
)

_VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": "Submit the fraud analysis verdict for a LINE message",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["fraud", "suspicious", "safe"],
                "description": (
                    "fraud = confirmed scam pattern with high confidence; "
                    "suspicious = likely scam or caution warranted; "
                    "safe = no clear fraud signals"
                ),
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score between 0.0 and 1.0",
            },
            "matched_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "KB document IDs used as evidence "
                    "(e.g. ['bank_phishing', 'delivery_scam']). "
                    "Empty list if no KB pattern matched."
                ),
            },
            "message_signals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Fraud signals detected in message wording",
            },
            "url_signals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Fraud signals from URL analysis",
            },
            "plain_summary": {
                "type": "string",
                "description": (
                    "Plain-language summary in Traditional Chinese for elderly users, "
                    "under 60 characters"
                ),
            },
            "domain_age_days": {
                "type": "integer",
                "description": "Domain age in days if known",
            },
        },
        "required": [
            "verdict",
            "confidence",
            "matched_patterns",
            "message_signals",
            "url_signals",
            "plain_summary",
        ],
    },
}


def infer_llm_prompt(prompt_text: str) -> FraudVerdict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is required for LLM inference.")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        tools=[_VERDICT_TOOL],
        tool_choice={"type": "tool", "name": "submit_verdict"},
        messages=[{"role": "user", "content": prompt_text}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_verdict":
            return FraudVerdict(**block.input)

    raise ValueError("LLM response did not contain a submit_verdict tool call")
