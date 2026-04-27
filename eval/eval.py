#!/usr/bin/env python3
"""Evaluation harness for Taiwan Fraud Detector.

Runs the analysis pipeline against a labeled test set and reports
precision, recall, and F1 — both overall and broken down by scam category.

Usage:
    python eval/eval.py [--skip-fetch]

Options:
    --skip-fetch   Skip URL fetching and WHOIS lookups (faster; for unit-level eval).

Results are written to eval/results.csv.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure the project root is on sys.path when run directly.
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

SKIP_FETCH = "--skip-fetch" in sys.argv

if SKIP_FETCH:
    # Monkeypatch before importing app so no network calls are made during eval.
    import unittest.mock as _mock
    import pipeline.scraper as _scraper_mod
    import pipeline.enricher as _enricher_mod
    _scraper_mod.fetch_page = _mock.Mock(return_value={"error": "eval_skipped", "text": "", "title": ""})
    _enricher_mod.get_domain_info = _mock.Mock(return_value={"domain_age_days": None, "registrar": None, "error": None})

from app import analyze_line_message  # noqa: E402 — import after optional patches


LABEL_CSV = Path(__file__).parent / "labeled_messages.csv"
RESULTS_CSV = Path(__file__).parent / "results.csv"

# Treat fraud + suspicious as "flagged" (positive class).
_POSITIVE_LABELS = {"fraud", "suspicious"}
_POSITIVE_VERDICTS = {"fraud", "suspicious"}


def _load_dataset(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _run_row(row: Dict[str, str]) -> Dict[str, Any]:
    verdict, confidence, summary, url, status, metadata, prompt, matched = analyze_line_message(
        row["message_text"]
    )
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


def main() -> None:
    if not LABEL_CSV.exists():
        print(f"Dataset not found: {LABEL_CSV}", file=sys.stderr)
        sys.exit(1)

    dataset = _load_dataset(LABEL_CSV)
    print(f"Loaded {len(dataset)} labeled messages.")
    if SKIP_FETCH:
        print("Mode: --skip-fetch (URL fetching and WHOIS disabled)\n")
    else:
        print("Mode: full pipeline (URL fetching enabled — may be slow)\n")

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
        print(f"  [{i:2d}/{len(dataset)}] {mark} label={result['label']:10s} verdict={result['verdict']}")

    print()
    overall = _metrics(results)
    _print_metrics("OVERALL", overall)

    categories = sorted({r["scam_category"] for r in results if r["scam_category"] and r["scam_category"] != "none"})
    if categories:
        print()
        for cat in categories:
            cat_results = [r for r in results if r["scam_category"] == cat]
            _print_metrics(cat, _metrics(cat_results))

    # Write results CSV.
    fieldnames = [
        "message_text", "label", "scam_category", "verdict", "confidence",
        "matched_patterns", "summary", "tp", "fp", "fn", "tn",
    ]
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults written to {RESULTS_CSV}")


if __name__ == "__main__":
    main()
