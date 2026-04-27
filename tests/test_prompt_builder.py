import unittest

from pipeline.prompt_builder import build_prompt


def _base_kwargs(**overrides) -> dict:
    kw = dict(
        message="這是測試訊息",
        message_signals=[],
        url="",
        url_status="ok",
        url_signals=[],
        url_metadata={},
        retrieved_docs=[],
    )
    kw.update(overrides)
    return kw


class TestPromptBuilder(unittest.TestCase):
    def test_build_prompt_includes_all_sections(self):
        retrieved_docs = [
            {
                "doc": {
                    "id": "government_impersonation",
                    "title": "假冒政府機構詐騙",
                    "content": "若收到要求提供身份證或轉帳連結，通常是詐騙手法。",
                },
                "score": 1.42,
            }
        ]
        prompt = build_prompt(
            message="請問這個連結是詐騙嗎？",
            message_signals=["中獎", "立即回覆"],
            url="https://example.com/offer",
            url_status="ok",
            url_signals=["帶有亂碼", "短域名"],
            url_metadata={
                "original_url": "https://t.co/abc123",
                "final_url": "https://example.com/offer",
                "redirect_hops": 2,
                "hostname": "example.com",
                "path": "/offer",
                "query": "id=123",
                "has_credentials": False,
            },
            retrieved_docs=retrieved_docs,
        )

        self.assertIn("使用者 LINE 訊息:", prompt)
        self.assertIn("網址資訊:", prompt)
        self.assertIn("知識庫檢索結果", prompt)
        self.assertIn("假冒政府機構詐騙", prompt)
        self.assertIn("網址驗證狀態: ok", prompt)
        self.assertIn("檢測到網址: https://example.com/offer", prompt)

    def test_build_prompt_handles_empty_retrieved_docs(self):
        prompt = build_prompt(**_base_kwargs(url_status="無"))
        self.assertIn("知識庫檢索結果: 無", prompt)
        self.assertIn("訊息信號: 無", prompt)
        self.assertIn("網址特徵: 無", prompt)

    def test_build_prompt_includes_kb_doc_id(self):
        retrieved_docs = [
            {
                "doc": {"id": "bank_phishing", "title": "銀行詐騙", "content": "測試內容"},
                "score": 2.0,
            }
        ]
        prompt = build_prompt(**_base_kwargs(retrieved_docs=retrieved_docs))
        self.assertIn("[bank_phishing]", prompt)

    # --- page_content ---

    def test_build_prompt_includes_page_content_section(self):
        prompt = build_prompt(**_base_kwargs(page_content="這是從詐騙頁面擷取的文字。"))
        self.assertIn("頁面內容 (節錄):", prompt)
        self.assertIn("這是從詐騙頁面擷取的文字。", prompt)

    def test_build_prompt_omits_page_section_when_empty(self):
        prompt = build_prompt(**_base_kwargs(page_content=""))
        self.assertNotIn("頁面內容 (節錄):", prompt)

    def test_build_prompt_omits_page_section_when_not_provided(self):
        prompt = build_prompt(**_base_kwargs())
        self.assertNotIn("頁面內容 (節錄):", prompt)

    # --- domain_info ---

    def test_build_prompt_includes_domain_age(self):
        prompt = build_prompt(**_base_kwargs(domain_info={"domain_age_days": 120, "registrar": "GoDaddy"}))
        self.assertIn("域名年齡: 120 天", prompt)
        self.assertIn("GoDaddy", prompt)

    def test_build_prompt_warns_on_young_domain(self):
        prompt = build_prompt(**_base_kwargs(domain_info={"domain_age_days": 5, "registrar": None}))
        self.assertIn("域名年齡: 5 天", prompt)
        self.assertIn("30天內剛創建", prompt)

    def test_build_prompt_no_warning_for_old_domain(self):
        prompt = build_prompt(**_base_kwargs(domain_info={"domain_age_days": 365, "registrar": None}))
        self.assertIn("域名年齡: 365 天", prompt)
        self.assertNotIn("不到30天", prompt)

    def test_build_prompt_omits_domain_section_when_age_unknown(self):
        prompt = build_prompt(**_base_kwargs(domain_info={"domain_age_days": None, "registrar": None}))
        self.assertNotIn("域名資訊:", prompt)

    def test_build_prompt_omits_domain_section_when_not_provided(self):
        prompt = build_prompt(**_base_kwargs())
        self.assertNotIn("域名資訊:", prompt)


if __name__ == "__main__":
    unittest.main()
