#!/usr/bin/env python3
"""Evaluation harness for Taiwan Fraud Detector.

Runs the analysis pipeline against a labeled test set and reports
precision, recall, and F1 — both overall and broken down by scam category.

Usage:
    python eval/eval.py [options]

Options:
    --skip-fetch           Skip URL fetching and WHOIS lookups (faster; for unit-level eval).
    --run-tag TAG          Label for this run saved to run_history.csv (e.g. "baseline-v1").
    --mode MODE            Ablation mode: full (default), message_only, url_only,
                           bm25_only, semantic_only, no_kb.
    --model MODEL          LLM model ID override (e.g. "claude-haiku-4-5-20251001").
    --output FILE          Override per-row results path (default: eval/results.csv).
    --limit N              Only run the first N rows (useful for smoke tests).

Results are written to eval/results.csv (per-row) and appended to
eval/run_history.csv (one-row-per-run summary).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import os
import sys
import unittest.mock as _mock
from pathlib import Path
from typing import Any, Dict, List

# Ensure the project root is on sys.path when run directly.
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Parse args early — we need mode flags before importing pipeline modules.
# ---------------------------------------------------------------------------

_parser = argparse.ArgumentParser(description="Taiwan Fraud Detector eval harness", add_help=False)
_parser.add_argument("--skip-fetch", action="store_true")
_parser.add_argument("--run-tag", default="")
_parser.add_argument("--mode", default="full",
                     choices=["full", "message_only", "url_only", "bm25_only", "semantic_only", "no_kb"])
_parser.add_argument("--model", default="")
_parser.add_argument("--output", default="")
_parser.add_argument("--limit", type=int, default=0)
_parser.add_argument("-h", "--help", action="help")
_args = _parser.parse_args()

SKIP_FETCH: bool = _args.skip_fetch
RUN_TAG: str = _args.run_tag or _args.mode
MODE: str = _args.mode
MODEL_OVERRIDE: str = _args.model
LIMIT: int = _args.limit

# ---------------------------------------------------------------------------
# Apply monkeypatches BEFORE importing app / pipeline.
# ---------------------------------------------------------------------------

_EMPTY_PAGE = {"error": "eval_skipped", "text": "", "title": ""}
_EMPTY_DOMAIN = {"domain_age_days": None, "registrar": None, "error": None}


def _patch_skip_fetch() -> None:
    import pipeline.scraper as _scraper_mod
    import pipeline.enricher as _enricher_mod
    import pipeline.fetcher_client as _fc
    _scraper_mod.fetch_page = _mock.Mock(return_value=_EMPTY_PAGE)
    _enricher_mod.get_domain_info = _mock.Mock(return_value=_EMPTY_DOMAIN)
    _fc.fetch_page = _mock.Mock(return_value=_EMPTY_PAGE)
    _fc.get_domain_info = _mock.Mock(return_value=_EMPTY_DOMAIN)


def _patch_message_only() -> None:
    """Disable URL branch and KB retrieval — message signals + LLM only."""
    import pipeline.scraper as _scraper_mod
    import pipeline.enricher as _enricher_mod
    import pipeline.fetcher_client as _fc
    import pipeline.retriever as _ret
    _scraper_mod.fetch_page = _mock.Mock(return_value=_EMPTY_PAGE)
    _enricher_mod.get_domain_info = _mock.Mock(return_value=_EMPTY_DOMAIN)
    _fc.fetch_page = _mock.Mock(return_value=_EMPTY_PAGE)
    _fc.get_domain_info = _mock.Mock(return_value=_EMPTY_DOMAIN)
    _ret.bm25_search = _mock.Mock(return_value=[])
    _ret.hybrid_search = _mock.Mock(return_value=[])


def _patch_url_only() -> None:
    """Disable message signals and KB retrieval — URL signals + LLM only."""
    import pipeline.signal_analyzer as _sig
    import pipeline.retriever as _ret
    _sig.analyze_message_signals = _mock.Mock(return_value=[])
    _ret.bm25_search = _mock.Mock(return_value=[])
    _ret.hybrid_search = _mock.Mock(return_value=[])


def _patch_bm25_only() -> None:
    """Force BM25 retrieval only — remove VOYAGE_API_KEY so hybrid_search falls back."""
    os.environ.pop("VOYAGE_API_KEY", None)


def _patch_semantic_only() -> None:
    """Use semantic search only — stub out BM25."""
    import pipeline.retriever as _ret
    _ret.bm25_search = _mock.Mock(return_value=[])


def _patch_no_kb() -> None:
    """Disable KB retrieval entirely — message signals + URL signals + LLM only."""
    import pipeline.retriever as _ret
    _ret.bm25_search = _mock.Mock(return_value=[])
    _ret.hybrid_search = _mock.Mock(return_value=[])


_PATCHES = {
    "full": None,
    "message_only": _patch_message_only,
    "url_only": _patch_url_only,
    "bm25_only": _patch_bm25_only,
    "semantic_only": _patch_semantic_only,
    "no_kb": _patch_no_kb,
}

if SKIP_FETCH:
    _patch_skip_fetch()

patch_fn = _PATCHES.get(MODE)
if patch_fn:
    patch_fn()

if MODEL_OVERRIDE:
    os.environ["EVAL_MODEL_OVERRIDE"] = MODEL_OVERRIDE

from app import analyze_line_message  # noqa: E402 — after patches


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

LABEL_CSV = Path(__file__).parent / "labeled_messages.csv"
RESULTS_CSV = Path(_args.output) if _args.output else Path(__file__).parent / "results.csv"
HISTORY_CSV = Path(__file__).parent / "run_history.csv"

_POSITIVE_LABELS = {"fraud", "suspicious"}
_POSITIVE_VERDICTS = {"fraud", "suspicious"}


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _load_dataset(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _run_row(row: Dict[str, str]) -> Dict[str, Any]:
    result = analyze_line_message(row["message_text"])
    verdict = result.verdict
    confidence = result.confidence
    summary = result.plain_summary
    matched = result.matched_patterns
    return {
        "message_text": row["message_text"][:80],
        "label": row["label"],
        "scam_category": row.get("scam_category", ""),
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "matched_patterns": matched,
        "summary": summary,
        "tp": int(row["label"] in _POSITIVE_LABELS and verdict in _POSITIVE_VERDICTS),
        "fp": int(row["label"] not in _POSITIVE_LABELS and verdict in _POSITIVE_VERDICTS),
        "fn": int(row["label"] in _POSITIVE_LABELS and verdict not in _POSITIVE_VERDICTS),
        "tn": int(row["label"] not in _POSITIVE_LABELS and verdict not in _POSITIVE_VERDICTS),
    }


def _metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    tp = sum(r["tp"] for r in results)
    fp = sum(r["fp"] for r in results)
    fn = sum(r["fn"] for r in results)
    tn = sum(r["tn"] for r in results)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "total": len(results),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


def _print_metrics(label: str, m: Dict[str, float]) -> None:
    print(
        f"{label:35s}  n={m['total']:3d}  "
        f"P={m['precision']:.3f}  R={m['recall']:.3f}  F1={m['f1']:.3f}  "
        f"(TP={m['tp']} FP={m['fp']} FN={m['fn']} TN={m['tn']})"
    )


def _append_history(
    run_tag: str,
    mode: str,
    model: str,
    skip_fetch: bool,
    n_total: int,
    overall: Dict[str, float],
    by_category: Dict[str, Dict[str, float]],
) -> None:
    fieldnames = [
        "timestamp", "run_tag", "mode", "model", "skip_fetch", "n_total",
        "precision", "recall", "f1", "tp", "fp", "fn", "tn",
    ]
    write_header = not HISTORY_CSV.exists() or HISTORY_CSV.stat().st_size == 0
    with open(HISTORY_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "run_tag": run_tag,
            "mode": mode,
            "model": model or os.getenv("EVAL_MODEL_OVERRIDE", "default"),
            "skip_fetch": skip_fetch,
            "n_total": n_total,
            **{k: overall[k] for k in ("precision", "recall", "f1", "tp", "fp", "fn", "tn")},
        })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not LABEL_CSV.exists():
        print(f"Dataset not found: {LABEL_CSV}", file=sys.stderr)
        sys.exit(1)

    dataset = _load_dataset(LABEL_CSV)
    if LIMIT:
        dataset = dataset[:LIMIT]

    print(f"Loaded {len(dataset)} labeled messages.")
    print(f"Mode: {MODE}" + (" + --skip-fetch" if SKIP_FETCH else ""))
    print(f"Run tag: {RUN_TAG or '(none)'}")
    if MODEL_OVERRIDE:
        print(f"Model override: {MODEL_OVERRIDE}")
    print()

    results: List[Dict[str, Any]] = []
    for i, row in enumerate(dataset, 1):
        try:
            result = _run_row(row)
        except Exception as exc:
            result = {
                "message_text": row["message_text"][:80],
                "label": row["label"],
                "scam_category": row.get("scam_category", ""),
                "verdict": "error",
                "confidence": 0.0,
                "matched_patterns": "",
                "summary": str(exc)[:100],
                "tp": 0, "fp": 0,
                "fn": int(row["label"] in _POSITIVE_LABELS),
                "tn": int(row["label"] not in _POSITIVE_LABELS),
            }
        results.append(result)
        mark = "✓" if result["tp"] or result["tn"] else "✗"
        print(
            f"  [{i:3d}/{len(dataset)}] {mark}  "
            f"label={result['label']:10s}  verdict={result['verdict']:10s}  "
            f"conf={result['confidence']:.2f}"
        )

    # Overall metrics
    print()
    overall = _metrics(results)
    _print_metrics("OVERALL", overall)

    # Per-category breakdown
    categories = sorted({
        r["scam_category"] for r in results
        if r["scam_category"] and r["scam_category"] != "none"
    })
    by_cat: Dict[str, Dict[str, float]] = {}
    if categories:
        print()
        for cat in categories:
            cat_results = [r for r in results if r["scam_category"] == cat]
            m = _metrics(cat_results)
            by_cat[cat] = m
            _print_metrics(cat, m)

    # Per-label-class breakdown
    print()
    for lbl in ["fraud", "suspicious", "safe"]:
        lbl_results = [r for r in results if r["label"] == lbl]
        if lbl_results:
            _print_metrics(f"  label={lbl}", _metrics(lbl_results))

    # Write per-row results
    fieldnames = [
        "message_text", "label", "scam_category", "verdict", "confidence",
        "matched_patterns", "summary", "tp", "fp", "fn", "tn",
    ]
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"\nPer-row results → {RESULTS_CSV}")

    # Append one-row summary to run_history.csv
    _append_history(RUN_TAG, MODE, MODEL_OVERRIDE, SKIP_FETCH, len(dataset), overall, by_cat)
    print(f"Run summary appended → {HISTORY_CSV}")


if __name__ == "__main__":
    main()
