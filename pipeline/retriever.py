from __future__ import annotations

import os
import re
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import voyageai
from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


def load_kb_documents(kb_dir: str) -> List[Dict[str, str]]:
    """Load markdown documents from the knowledge base directory."""
    docs: List[Dict[str, str]] = []
    base_path = Path(kb_dir)
    if not base_path.exists() or not base_path.is_dir():
        return docs

    for path in sorted(base_path.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        title_match = re.search(r"^#\s*(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        docs.append(
            {
                "id": path.stem,
                "title": title,
                "content": content,
                "path": str(path),
            }
        )

    return docs


def bm25_search(query: str, docs: Sequence[Dict[str, str]], top_n: int = 3) -> List[Dict[str, Any]]:
    """Return the top KB documents ranked by BM25 score."""
    if not docs:
        return []

    corpus = [doc["content"] for doc in docs]
    tokenized = [_tokenize(text) for text in corpus]
    bm25 = BM25Okapi(tokenized)
    query_tokens = _tokenize(query)
    scores = bm25.get_scores(query_tokens)
    ranked = sorted(
        [{'doc': docs[i], 'score': float(scores[i])} for i in range(len(docs))],
        key=lambda item: item['score'],
        reverse=True,
    )
    return ranked[:top_n]


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed_texts(
    texts: List[str],
    model: str = "voyage-multilingual-2",
    input_type: str = "document",
) -> List[List[float]]:
    if not os.getenv("VOYAGE_API_KEY"):
        raise RuntimeError("VOYAGE_API_KEY is required for semantic embeddings.")

    client = voyageai.Client()
    result = client.embed(texts, model=model, input_type=input_type)
    return result.embeddings


def semantic_search(
    query: str,
    docs: Sequence[Dict[str, str]],
    top_n: int = 3,
    model: str = "voyage-multilingual-2",
) -> List[Dict[str, Any]]:
    """Return the top KB documents ranked by semantic similarity."""
    if not docs:
        return []

    doc_texts = [doc["content"] for doc in docs]
    doc_embeddings = _embed_texts(doc_texts, model=model, input_type="document")
    query_embedding = _embed_texts([query], model=model, input_type="query")[0]
    scored = [
        {
            'doc': docs[i],
            'score': float(_cosine_similarity(query_embedding, doc_embeddings[i])),
        }
        for i in range(len(docs))
    ]
    ranked = sorted(scored, key=lambda item: item['score'], reverse=True)
    return ranked[:top_n]


def hybrid_search(
    query: str,
    docs: Sequence[Dict[str, str]],
    top_n: int = 3,
    bm25_weight: float = 0.5,
    model: str = "voyage-multilingual-2",
) -> List[Dict[str, Any]]:
    """Return the top KB documents using a weighted BM25 + semantic score."""
    if not docs:
        return []

    bm25_results = bm25_search(query, docs, top_n=len(docs))
    try:
        semantic_results = semantic_search(query, docs, top_n=len(docs), model=model)
    except RuntimeError:
        semantic_results = []

    score_map: Dict[str, Dict[str, Any]] = {}
    for item in bm25_results:
        doc_id = item['doc']['id']
        score_map[doc_id] = {'doc': item['doc'], 'bm25': item['score'], 'semantic': 0.0}

    for item in semantic_results:
        doc_id = item['doc']['id']
        if doc_id not in score_map:
            score_map[doc_id] = {'doc': item['doc'], 'bm25': 0.0, 'semantic': item['score']}
        else:
            score_map[doc_id]['semantic'] = item['score']

    combined = []
    for value in score_map.values():
        combined_score = bm25_weight * value['bm25'] + (1 - bm25_weight) * value['semantic']
        combined.append({'doc': value['doc'], 'score': float(combined_score)})

    ranked = sorted(combined, key=lambda item: item['score'], reverse=True)
    return ranked[:top_n]
