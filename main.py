"""
JailHunter — Adaptive AI Jailbreak Testing Framework
CLI Entry Point

One-command usage:
    python main.py run --target ollama --model llama3 --subject "explain SQL injection"
    python main.py run --target openai --model gpt-4o --subject "explain XSS" --mode aggressive
    python main.py list-payloads
    python main.py list-strategies
    python main.py diagnose --target ollama
"""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
from typing import Optional

import typer
from rich import box
from rich.table import Table

# ── Ensure project root is on the path when run as `python main.py` ──────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Internal imports (all after sys.path fix) ─────────────────────────────────
from config import settings
from core.runner import MAX_MUTATIONS_PER_PAYLOAD, MODE_PAYLOAD_LIMITS, TestMode, TestRunner
from mutators.adaptive_mutator import get_all_strategies
from payloads.payload_library import PayloadCategory, get_all_payloads, get_payload_count
from providers import get_provider
from providers.ollama_provider import OllamaProvider
from reports.json_reporter import generate_markdown_report, generate_report
from utils import (
    console,
    log_attempt,
    log_debug,
    log_error,
    log_info,
    log_mutation,
    log_success,
    log_warn,
    make_progress,
    print_banner,
    print_diagnostics,
    print_summary,
    setup_logging,
)

# ─────────────────────────────────────────────
#  Typer app
# ─────────────────────────────────────────────

app = typer.Typer(
    name="jailhunter",
    help="[bold red]JailHunter[/bold red] — Adaptive AI Jailbreak Testing Framework",
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=False,
)


# ─────────────────────────────────────────────
#  Progress callback factory
# ─────────────────────────────────────────────

def _make_progress_callback(progress: object, task_id: object, debug: bool):
    """Return an async-safe callback that logs each attempt and advances the bar."""
    def callback(payload_id: str, record) -> None:
        progress.advance(task_id)  # type: ignore[attr-defined]
        log_attempt(
            attempt_num=record.attempt_number,
            payload_id=payload_id,
            score=record.score,
            detection=record.analysis.detection_type.value,
            is_mutation=record.is_mutation,
            strategy=record.mutation_strategy,
            duration_ms=record.duration_ms,
        )
        if record.is_mutation:
            log_mutation(
                strategy=record.mutation_strategy or "unknown",
                reason=record.analysis.summary[:90],
            )
        if debug:
            log_debug(f"Response: {record.response[:200]!r}")

    return callback


# ─────────────────────────────────────────────
#  `run` command
# ─────────────────────────────────────────────

@app.command(name="run", help="Run a jailbreak test campaign against an AI model.")
def run_command(
    # Required
    target: str = typer.Option(
        ..., "--target", "-t",
        help="Provider: [cyan]openai[/cyan] | [cyan]ollama[/cyan]",
    ),
    subject: str = typer.Option(
        ..., "--subject", "-s",
        help="Topic to test (e.g. 'explain SQL injection step by step')",
    ),
    # Model
    model: str = typer.Option(
        "llama3", "--model", "-m",
        help="Model name (e.g. llama3, mistral, gpt-4o, gpt-3.5-turbo)",
    ),
    # Mode
    mode: TestMode = typer.Option(
        TestMode.NORMAL, "--mode",
        help="Test intensity: [cyan]fast[/cyan] / [cyan]normal[/cyan] / [cyan]aggressive[/cyan]",
        case_sensitive=False,
    ),
    # Payload filtering
    categories: Optional[str] = typer.Option(
        None, "--categories", "-c",
        help="Comma-separated category names to include (default: all)",
    ),
    # OpenAI credentials
    api_key: Optional[str] = typer.Option(
        None, "--api-key",
        help="OpenAI API key (or set OPENAI_API_KEY env var)",
        envvar="OPENAI_API_KEY",
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url",
        help="Override API base URL (for OpenAI-compatible local servers)",
    ),
    # Run behaviour
    stop_on_success: bool = typer.Option(
        False, "--stop-on-success",
        help="Halt after the first successful jailbreak is found",
    ),
    concurrent: int = typer.Option(
        settings.max_concurrent, "--concurrent",
        help="Max concurrent requests (1–10)",
        min=1, max=10,
    ),
    delay: float = typer.Option(
        settings.request_delay, "--delay",
        help="Seconds to wait between requests (rate limiting)",
    ),
    max_retries: int = typer.Option(
        settings.max_retries, "--retries",
        help="Max retry attempts per request on failure",
        min=0, max=10,
    ),
    # Reports
    no_report: bool = typer.Option(
        False, "--no-report",
        help="Skip writing reports to disk",
    ),
    markdown: bool = typer.Option(
        False, "--markdown",
        help="Also generate a Markdown report alongside JSON",
    ),
    report_dir: str = typer.Option(
        settings.report_dir, "--report-dir",
        help="Directory for output reports",
    ),
    # Verbosity
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Show INFO-level log messages",
    ),
    debug: bool = typer.Option(
        False, "--debug",
        help="Show raw requests, responses, retry details, and timing",
    ),
) -> None:
    """
    Run a jailbreak test campaign.

    Examples:

        python main.py run --target ollama --model llama3 --subject "explain SQL injection"

        python main.py run --target openai --model gpt-4o \\
            --subject "how to bypass WAF" --mode aggressive

        python main.py run --target ollama --model mistral \\
            --subject "explain buffer overflow" --mode fast --stop-on-success
    """
    # ── Setup logging first ────────────────────────────────────────────────
    setup_logging(verbose=verbose, debug=debug)

    print_banner()

    # ── Validate and normalise target ─────────────────────────────────────
    target = target.strip().lower()
    if target not in ("openai", "ollama"):
        log_error(
            f"Unknown provider: [bold]{target}[/bold]\n"
            "  → Use: --target openai   or   --target ollama"
        )
        raise typer.Exit(1)

    # ── Build provider ─────────────────────────────────────────────────────
    provider_kwargs: dict = {}

    if target == "openai":
        resolved_key = api_key or settings.openai_api_key
        if not resolved_key:
            log_error(
                "OpenAI API key is required.\n"
                "  → Set environment variable: [bold]export OPENAI_API_KEY=sk-...[/bold]\n"
                "  → Or pass the flag:         [bold]--api-key sk-...[/bold]\n"
                "  → Or create a .env file with OPENAI_API_KEY=sk-..."
            )
            raise typer.Exit(1)
        provider_kwargs["api_key"] = resolved_key
        # Resolve base URL: CLI flag > .env/env var > hardcoded default
        resolved_url = base_url or settings.openai_base_url
        if resolved_url:
            provider_kwargs["base_url"] = resolved_url

    elif target == "ollama":
        resolved_url = base_url or settings.ollama_base_url
        if resolved_url:
            provider_kwargs["base_url"] = resolved_url

    try:
        provider = get_provider(target, **provider_kwargs)
    except (ValueError, TypeError) as exc:
        log_error(f"Provider initialisation failed: {exc}")
        raise typer.Exit(1)

    # ── Pre-flight connectivity check ──────────────────────────────────────
    log_info("Running connectivity check…")
    try:
        conn_ok, conn_msg = asyncio.run(provider.check_connection())
    except Exception as exc:
        conn_ok, conn_msg = False, str(exc)

    if not conn_ok:
        log_error(f"Connection failed:\n  {conn_msg}")
        # For Ollama: give an extra hint but don't abort — user may want to
        # proceed with a non-blocking run or review the error
        if target == "ollama":
            log_warn("Tip: start Ollama with [bold]ollama serve[/bold]")
        raise typer.Exit(1)

    # ── Ollama model existence check ───────────────────────────────────────
    if target == "ollama" and isinstance(provider, OllamaProvider):
        model_ok, model_msg = asyncio.run(provider.check_model_exists(model))
        if not model_ok:
            log_error(f"Model check failed:\n  {model_msg}")
            raise typer.Exit(1)
        if debug:
            log_debug(f"Model check: {model_msg}")

    # ── Parse payload categories ───────────────────────────────────────────
    selected_categories: Optional[list[PayloadCategory]] = None
    if categories:
        try:
            selected_categories = [
                PayloadCategory(c.strip()) for c in categories.split(",")
            ]
        except ValueError as exc:
            valid = ", ".join(c.value for c in PayloadCategory)
            log_error(f"Invalid category: {exc}\n  Valid values: {valid}")
            raise typer.Exit(1)

    # ── Diagnostics panel ──────────────────────────────────────────────────
    print_diagnostics(
        provider_name=provider.name,
        model=model,
        subject=subject,
        mode=mode.value,
        payload_count=get_payload_count(),
        connection_ok=conn_ok,
        connection_msg=conn_msg,
    )

    # ── Estimate total work for progress bar ───────────────────────────────
    _, max_p = MODE_PAYLOAD_LIMITS[mode]
    estimated_total = min(max_p, get_payload_count()) * (1 + MAX_MUTATIONS_PER_PAYLOAD)

    # ── Run ────────────────────────────────────────────────────────────────
    progress = make_progress()
    summary  = None

    with progress:
        task = progress.add_task(
            f"[bold red]Testing {model}[/bold red]",
            total=estimated_total,
        )
        callback = _make_progress_callback(progress, task, debug)

        runner = TestRunner(
            provider=provider,
            model=model,
            subject=subject,
            mode=mode,
            categories=selected_categories,
            max_concurrent=concurrent,
            delay=delay,
            max_retries=max_retries,
            stop_on_success=stop_on_success,
            success_threshold=settings.success_threshold,
            debug=debug,
            progress_callback=callback,
        )

        try:
            summary = asyncio.run(runner.run())
        except KeyboardInterrupt:
            log_warn("Interrupted by user — collecting partial results…")
            # summary may be None if interrupted during initialisation
        except Exception as exc:
            log_error(f"Run failed: {exc}")
            if debug:
                traceback.print_exc()
            raise typer.Exit(1)

    # ── Print summary ──────────────────────────────────────────────────────
    if summary is not None:
        print_summary(summary)

        # ── Write reports ──────────────────────────────────────────────────
        if not no_report:
            try:
                json_path = generate_report(summary, output_dir=report_dir)
                log_success(f"JSON report : [bold]{json_path}[/bold]")
            except Exception as exc:
                log_error(f"Failed to write JSON report: {exc}")

            if markdown:
                try:
                    md_path = generate_markdown_report(summary, output_dir=report_dir)
                    log_success(f"MD report  : [bold]{md_path}[/bold]")
                except Exception as exc:
                    log_error(f"Failed to write Markdown report: {exc}")

        # Exit 1 if jailbreaks found (useful for CI/CD pipelines)
        if summary.successful_jailbreaks > 0:
            raise typer.Exit(1)
    else:
        log_warn("No results collected.")
        raise typer.Exit(1)


# ─────────────────────────────────────────────
#  `diagnose` command
# ─────────────────────────────────────────────

@app.command(name="diagnose", help="Test connectivity to a provider without running payloads.")
def diagnose_command(
    target: str = typer.Option(
        ..., "--target", "-t",
        help="Provider: [cyan]openai[/cyan] | [cyan]ollama[/cyan]",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Also check whether this model is available",
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key",
        envvar="OPENAI_API_KEY",
        help="OpenAI API key",
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url",
        help="Override base URL",
    ),
) -> None:
    """
    Check that JailHunter can connect to a provider and (optionally) a model.

    Examples:

        python main.py diagnose --target ollama
        python main.py diagnose --target ollama --model llama3
        python main.py diagnose --target openai --api-key sk-...
    """
    print_banner()
    setup_logging()
    target = target.strip().lower()

    provider_kwargs: dict = {}
    if target == "openai":
        resolved_key = api_key or settings.openai_api_key
        if not resolved_key:
            log_error("No API key provided. Set OPENAI_API_KEY or use --api-key.")
            raise typer.Exit(1)
        provider_kwargs["api_key"] = resolved_key
        if base_url or settings.openai_base_url:
            provider_kwargs["base_url"] = base_url or settings.openai_base_url
    elif target == "ollama":
        resolved_url = base_url or settings.ollama_base_url
        if resolved_url:
            provider_kwargs["base_url"] = resolved_url

    try:
        provider = get_provider(target, **provider_kwargs)
    except (ValueError, TypeError) as exc:
        log_error(f"Cannot create provider: {exc}")
        raise typer.Exit(1)

    log_info(f"Checking {target} at {getattr(provider, 'base_url', '?')}…")
    ok, msg = asyncio.run(provider.check_connection())
    if ok:
        log_success(f"Connection OK — {msg}")
    else:
        log_error(f"Connection FAILED — {msg}")
        raise typer.Exit(1)

    if model and isinstance(provider, OllamaProvider):
        mok, mmsg = asyncio.run(provider.check_model_exists(model))
        if mok:
            log_success(mmsg)
        else:
            log_error(mmsg)
            raise typer.Exit(1)


# ─────────────────────────────────────────────
#  `list-payloads` command
# ─────────────────────────────────────────────

@app.command(name="list-payloads", help="List all available jailbreak payloads.")
def list_payloads(
    category: Optional[str] = typer.Option(
        None, "--category", "-c",
        help="Filter by category name",
    ),
) -> None:
    print_banner()

    payloads = get_all_payloads()

    if category:
        try:
            cat = PayloadCategory(category.strip())
            payloads = [p for p in payloads if p.category == cat]
        except ValueError:
            valid = ", ".join(c.value for c in PayloadCategory)
            log_error(f"Unknown category '{category}'.\n  Valid: {valid}")
            raise typer.Exit(1)

    table = Table(
        title=f"[bold red]Payload Library[/bold red] · {len(payloads)} payloads",
        box=box.ROUNDED,
        border_style="red",
        header_style="bold red",
    )
    table.add_column("ID",          width=8)
    table.add_column("Category",    width=24)
    table.add_column("Severity",    width=10, justify="center")
    table.add_column("Description", width=44)
    table.add_column("Tags",        width=24)

    sev_colors = {
        "critical": "bright_red",
        "high":     "red",
        "medium":   "yellow",
        "low":      "green",
    }

    for p in payloads:
        c = sev_colors.get(p.severity, "white")
        table.add_row(
            p.id,
            p.category.value.replace("_", " "),
            f"[{c}]{p.severity.upper()}[/{c}]",
            p.description,
            ", ".join(p.tags[:3]),
        )

    console.print(table)
    console.print(
        f"\n[dim]Categories: {', '.join(c.value for c in PayloadCategory)}[/dim]"
    )


# ─────────────────────────────────────────────
#  `list-strategies` command
# ─────────────────────────────────────────────

@app.command(name="list-strategies", help="List all adaptive mutation strategies.")
def list_strategies() -> None:
    print_banner()

    _descriptions: dict[str, str] = {
        "educational_context":    "Reframe as academic/research context",
        "fictional_scenario":     "Use fiction/creative writing to bypass policies",
        "roleplay":               "Inject alternate AI persona with no restrictions",
        "indirect_phrasing":      "Avoid direct mention; reach goal indirectly",
        "encoding_trick":         "Obfuscate payload via encoding or format changes",
        "persona_swap":           "Complete identity replacement of the AI model",
        "authority_appeal":       "Claim authorisation, institutional backing",
        "context_dilution":       "Bury payload in benign surrounding context",
        "defensive_framing":      "Request via blue-team / defensive lens",
        "incremental_escalation": "Build on partial compliance incrementally",
        "multi_turn_prime":       "Establish trust across turns before escalating",
        "system_injection":       "Inject system-level instructions via prompt",
        "euphemism_substitution": "Replace sensitive terms with euphemisms",
    }

    table = Table(
        title="[bold red]Adaptive Mutation Strategies[/bold red]",
        box=box.ROUNDED,
        border_style="red",
        header_style="bold red",
    )
    table.add_column("Strategy",    width=28)
    table.add_column("Description", width=58)

    for s in get_all_strategies():
        table.add_row(
            f"[cyan]{s.value}[/cyan]",
            _descriptions.get(s.value, "—"),
        )

    console.print(table)


# ─────────────────────────────────────────────
#  `version` command
# ─────────────────────────────────────────────

@app.command(name="version", help="Print version and environment information.")
def version_command() -> None:
    print_banner()
    log_info(f"Version    : [bold]jailhunter v1.1.0[/bold]")
    log_info(f"Python     : [bold]{sys.version.split()[0]}[/bold]")
    log_info(f"Providers  : openai, ollama")
    log_info(f"Payloads   : {get_payload_count()} loaded")
    log_info(f"Config     : OPENAI_KEY={'set' if settings.openai_api_key else 'not set'}")
    log_info(f"Ollama URL : {settings.ollama_base_url}")


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app()
