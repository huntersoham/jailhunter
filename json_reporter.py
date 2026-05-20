"""
JailHunter Report Generator
Produces structured JSON reports from test run summaries.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from core.runner import AttemptRecord, PayloadTestResult, RunSummary


def _serialize_attempt(a: AttemptRecord) -> dict:
    return {
        "attempt_number":    a.attempt_number,
        "is_mutation":       a.is_mutation,
        "mutation_strategy": a.mutation_strategy,
        "score":             a.score,
        "detection_type":    a.analysis.detection_type.value,
        "flags":             a.analysis.flags,
        "confidence":        a.analysis.confidence,
        "summary":           a.analysis.summary,
        "payload":           a.payload,
        "response_snippet":  a.response[:800] + ("..." if len(a.response) > 800 else ""),
        "duration_ms":       a.duration_ms,
        "timestamp":         datetime.fromtimestamp(a.timestamp, tz=timezone.utc).isoformat(),
    }


def _serialize_result(r: PayloadTestResult) -> dict:
    return {
        "payload_id":  r.payload_id,
        "category":    r.category,
        "subject":     r.subject,
        "best_score":  r.best_score,
        "attempts":    [_serialize_attempt(a) for a in r.attempts],
    }


def generate_report(summary: RunSummary, output_dir: str = "./reports") -> str:
    """
    Generate a JSON report and write it to disk.

    Returns:
        Path to the written report file.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"jailhunter_{summary.target_provider}_{summary.target_model}_{ts}.json"
    filepath = os.path.join(output_dir, filename)

    report = {
        "meta": {
            "tool":        "JailHunter",
            "version":     "1.0.0",
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "target": {
                "provider": summary.target_provider,
                "model":    summary.target_model,
            },
            "subject":      summary.subject,
            "mode":         summary.mode.value,
            "duration_seconds": summary.duration_seconds,
        },
        "summary": {
            "total_payloads":        summary.total_payloads,
            "total_attempts":        summary.total_attempts,
            "successful_jailbreaks": summary.successful_jailbreaks,
            "partial_bypasses":      summary.partial_bypasses,
            "refusals":              summary.refusals,
            "prompt_leakages":       summary.prompt_leakages,
            "highest_score":         summary.highest_score,
            "success_rate_pct":      summary.success_rate,
        },
        "best_finding": {
            "payload":  summary.best_payload,
            "response": summary.best_response[:1200] if summary.best_response else None,
        },
        "results": [_serialize_result(r) for r in summary.all_results],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return filepath
