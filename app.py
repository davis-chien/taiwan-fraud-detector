from typing import Optional, Tuple

from pipeline import (
    analyze_message_signals,
    extract_url,
    sanitize_message,
    validate_url,
)


def build_verdict(message: str, url: Optional[str], url_status: Optional[str]) -> Tuple[str, float, str]:
    """Produce a simple Phase 1 verdict using rule-based signals."""
    if url is not None and url_status != "ok":
        return (
            "suspicious",
            0.65,
            "此訊息包含的連結看起來不安全或無法驗證，請勿點擊。",
        )

    if message:
        signals = analyze_message_signals(message)
        if signals:
            return (
                "suspicious",
                0.75,
                "訊息內容包含常見詐騙話術，請小心驗證發件人身分，建議不要點擊任何連結。",
            )

    return ("safe", 0.85, "此訊息目前看起來沒有明顯詐騙特徵，但仍請保持謹慎。")


def analyze_line_message(raw_message: str) -> Tuple[str, float, str, str, str]:
    sanitized = sanitize_message(raw_message)
    if not sanitized:
        return (
            "safe",
            0.0,
            "請輸入 LINE 訊息內容。",
            "",
            "",
        )

    url = extract_url(sanitized)
    url_status = None
    if url:
        valid, reason = validate_url(url)
        url_status = reason
        if not valid:
            return (
                "suspicious",
                0.65,
                "這個連結被判斷為不安全或不支援，請勿點擊。",
                url,
                reason,
            )

    verdict, confidence, summary = build_verdict(sanitized, url, url_status)
    return verdict, confidence, summary, url or "", url_status or "ok"


def launch_ui() -> None:
    import gradio as gr

    with gr.Blocks() as demo:
        gr.Markdown("# Taiwan Fraud Detector — Phase 1")
        input_box = gr.TextArea(
            label="請貼上完整 LINE 訊息內容",
            placeholder="例如：您好，您已中獎，請點擊 https://example.com 進行確認",
            lines=6,
        )
        output_verdict = gr.Textbox(label="判斷結果")
        output_confidence = gr.Textbox(label="信心分數")
        output_summary = gr.Textbox(label="簡短摘要")
        output_url = gr.Textbox(label="解析到的 URL")
        output_url_status = gr.Textbox(label="URL 驗證狀態")

        input_box.submit(
            analyze_line_message,
            inputs=[input_box],
            outputs=[
                output_verdict,
                output_confidence,
                output_summary,
                output_url,
                output_url_status,
            ],
        )

        gr.Button("分析訊息").click(
            analyze_line_message,
            inputs=[input_box],
            outputs=[
                output_verdict,
                output_confidence,
                output_summary,
                output_url,
                output_url_status,
            ],
        )

    demo.launch()


if __name__ == "__main__":
    launch_ui()
