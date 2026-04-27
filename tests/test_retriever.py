import os
import tempfile
import unittest
from unittest.mock import patch

from pipeline.retriever import (
    bm25_search,
    hybrid_search,
    load_kb_documents,
    semantic_search,
)


class TestRetriever(unittest.TestCase):
    def test_load_kb_documents_reads_markdown_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "example.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Example Title\n\nThis is a sample document.")

            docs = load_kb_documents(tmpdir)
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0]["id"], "example")
            self.assertEqual(docs[0]["title"], "Example Title")
            self.assertIn("sample document", docs[0]["content"])

    def test_bm25_search_ranked_results(self):
        docs = [
            {"id": "a", "title": "A", "content": "銀行 登入 驗證"},
            {"id": "b", "title": "B", "content": "包裹 運費 物流"},
            {"id": "c", "title": "C", "content": "中獎 禮券 免費"},
        ]
        results = bm25_search("銀行 登入", docs, top_n=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["doc"]["id"], "a")

    @patch("pipeline.retriever._embed_texts")
    def test_semantic_search_ranked_results(self, mock_embed_texts):
        mock_embed_texts.side_effect = [
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            [[1.0, 0.0, 0.0]],
        ]
        docs = [
            {"id": "a", "title": "A", "content": "銀行 登入 驗證"},
            {"id": "b", "title": "B", "content": "包裹 運費 物流"},
            {"id": "c", "title": "C", "content": "中獎 禮券 免費"},
        ]
        results = semantic_search("銀行 登入", docs, top_n=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["doc"]["id"], "a")

    @patch("pipeline.retriever._embed_texts")
    def test_hybrid_search_blends_scores(self, mock_embed_texts):
        mock_embed_texts.side_effect = [
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            [[1.0, 0.0, 0.0]],
        ]
        docs = [
            {"id": "a", "title": "A", "content": "銀行 登入 驗證"},
            {"id": "b", "title": "B", "content": "包裹 運費 物流"},
            {"id": "c", "title": "C", "content": "中獎 禮券 免費"},
        ]
        results = hybrid_search("銀行 登入", docs, top_n=2, bm25_weight=0.5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["doc"]["id"], "a")


if __name__ == "__main__":
    unittest.main()
