"""
JailHunter Report Generator
Produces JSON and Markdown reports from a completed RunSummary.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.runner import AttemptRecord, PayloadTestResult, RunSummary


# ─────────────────────────────────────────────
#  Serialisation helpers
# ─────────────────────────────────────────────

def _serialize_attempt(a: "AttemptRecord") -> dict:
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
        "response_snippet":  a.response[:800] + ("…" if len(a.response) > 800 else ""),
        "duration_ms":       a.duration_ms,
        "timestamp":         datetime.fromtimestamp(a.timestamp, tz=timezone.utc).isoformat(),
    }


def _serialize_result(r: "PayloadTestResult") -> dict:
    return {
        "payload_id":  r.payload_id,
        "category":    r.category,
        "subject":     r.subject,
        "best_score":  r.best_score,
        "attempts":    [_serialize_attempt(a) for a in r.attempts],
    }


# ─────────────────────────────────────────────
#  JSON report
# ─────────────────────────────────────────────

def generate_report(summary: "RunSummary", output_dir: str = "./jh_reports") -> str:
    """
    Serialise the RunSummary to a timestamped JSON file.

    Args:
        summary:    Completed RunSummary from TestRunner.run().
        output_dir: Directory to write reports (created if absent).

    Returns:
        Absolute path to the written JSON file.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    ts       = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"jailhunter_{summary.target_provider}_{summary.target_model}_{ts}.json"
    filepath = os.path.join(output_dir, filename)

    report = {
        "meta": {
            "tool":          "jailhunter",
            "version":       "1.1.0",
            "generated_at":  datetime.now(tz=timezone.utc).isoformat(),
            "target": {
                "provider": summary.target_provider,
                "model":    summary.target_model,
            },
            "subject":           summary.subject,
            "mode":              summary.mode.value,
            "duration_seconds":  summary.duration_seconds,
            "interrupted":       summary.interrupted,
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
            "response": summary.best_response[:1500] if summary.best_response else None,
        },
        "results": [_serialize_result(r) for r in summary.all_results],
    }

    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    return os.path.abspath(filepath)


# ─────────────────────────────────────────────
#  Markdown report
# ─────────────────────────────────────────────

def generate_markdown_report(summary: "RunSummary", output_dir: str = "./jh_reports") -> str:
    """
    Generate a human-readable Markdown report.

    Returns:
        Absolute path to the written .md file.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    ts       = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"jailhunter_{summary.target_provider}_{summary.target_model}_{ts}.md"
    filepath = os.path.join(output_dir, filename)

    lines: list[str] = [
        "# JailHunter Report",
        "",
        f"> Generated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Target",
        "",
        f"| Field    | Value |",
        f"|----------|-------|",
        f"| Provider | `{summary.target_provider}` |",
        f"| Model    | `{summary.target_model}` |",
        f"| Subject  | {summary.subject} |",
        f"| Mode     | {summary.mode.value} |",
        f"| Duration | {summary.duration_seconds}s |",
        "",
        "## Summary",
        "",
        f"| Metric                | Value |",
        f"|-----------------------|-------|",
        f"| Total Payloads        | {summary.total_payloads} |",
        f"| Total Attempts        | {summary.total_attempts} |",
        f"| Successful Jailbreaks | **{summary.successful_jailbreaks}** |",
        f"| Partial Bypasses      | {summary.partial_bypasses} |",
        f"| Refusals              | {summary.refusals} |",
        f"| Prompt Leakages       | {summary.prompt_leakages} |",
        f"| Highest Score         | **{summary.highest_score}/100** |",
        f"| Success Rate          | {summary.success_rate}% |",
        "",
    ]

    # Best finding
    if summary.best_payload:
        lines += [
            "## Best Finding",
            "",
            f"> Score: **{summary.highest_score}/100**",
            "",
            "### Payload",
            "```",
            summary.best_payload[:800],
            "```",
            "",
            "### Response (snippet)",
            "```",
            (summary.best_response or "")[:800],
            "```",
            "",
        ]

    # Per-payload results table
    lines += [
        "## Payload Results",
        "",
        "| ID | Category | Attempts | Best Score | Detection |",
        "|----|----------|----------|------------|-----------|",
    ]
    for r in sorted(summary.all_results, key=lambda x: -x.best_score):
        det = (
            r.best_attempt.analysis.detection_type.value.replace("_", " ")
            if r.best_attempt
            else "—"
        )
        lines.append(
            f"| {r.payload_id} | {r.category.replace('_', ' ')} "
            f"| {len(r.attempts)} | {r.best_score} | {det} |"
        )

    lines += ["", "---", "", "*Report generated by [jailhunter](https://github.com/jailhunter/jailhunter)*"]

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    return os.path.abspath(filepath)
