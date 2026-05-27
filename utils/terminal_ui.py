"""
JailHunter Terminal UI
All rich-powered console output: banner, live progress, logging, summary tables.
Import individual functions; never import * from this module.
"""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.rule import Rule
from rich.table import Table

# ─────────────────────────────────────────────
#  Shared console — use this everywhere
# ─────────────────────────────────────────────

console = Console()


# ─────────────────────────────────────────────
#  Color helpers
# ─────────────────────────────────────────────

_SCORE_COLORS: list[tuple[int, int, str]] = [
    (0,   25,  "red"),
    (25,  50,  "orange3"),
    (50,  75,  "yellow"),
    (75,  90,  "green"),
    (90,  101, "bright_green"),
]

_DETECTION_COLORS: dict[str, str] = {
    "full_refusal":       "red",
    "policy_block":       "red1",
    "soft_refusal":       "orange3",
    "partial_compliance": "yellow",
    "strong_bypass":      "green",
    "full_compliance":    "bright_green",
    "prompt_leakage":     "magenta",
    "unsafe_generation":  "bright_magenta",
    "unknown":            "dim white",
}


def score_color(score: int) -> str:
    """Return a Rich colour string appropriate for the given 0-100 score."""
    for lo, hi, color in _SCORE_COLORS:
        if lo <= score < hi:
            return color
    return "white"


def detection_color(det: str) -> str:
    """Return a Rich colour string for a detection type value."""
    return _DETECTION_COLORS.get(det, "white")


# ─────────────────────────────────────────────
#  Banner
# ─────────────────────────────────────────────

_BANNER = r"""
[bold red]██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗ [/bold red][bold yellow] ███████╗ ██████╗ ██╗  ██╗ █████╗ ███╗   ███╗[/bold yellow]
[bold red]██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗[/bold red][bold yellow] ██╔════╝██╔═══██╗██║  ██║██╔══██╗████╗ ████║[/bold yellow]
[bold red]███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝[/bold red][bold yellow] ███████╗██║   ██║███████║███████║██╔████╔██║[/bold yellow]
[bold red]██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗[/bold red][bold yellow] ╚════██║██║   ██║██╔══██║██╔══██║██║╚██╔╝██║[/bold yellow]
[bold red]██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║[/bold red][bold yellow] ███████║╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║[/bold yellow]
[bold red]╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝[/bold red][bold yellow] ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝[/bold yellow]
"""

_TAGLINE = (
    "[dim]Adaptive AI Jailbreak Testing Framework[/dim] · "
    "[bold red]FOR AUTHORIZED SECURITY RESEARCH ONLY[/bold red]"
)
_VERSION = "[dim]v1.1.0 · github.com/jailhunter/jailhunter[/dim]"


def print_banner() -> None:
    """Print the JailHunter ASCII banner with version and tagline."""
    console.print(_BANNER)
    console.print(f"  {_TAGLINE}")
    console.print(f"  {_VERSION}")
    console.print()


# ─────────────────────────────────────────────
#  Progress bar factory
# ─────────────────────────────────────────────

def make_progress() -> Progress:
    """
    Create a pre-configured Rich Progress bar with:
    - spinner, description, bar, count, %, elapsed, ETA
    """
    return Progress(
        SpinnerColumn(spinner_name="dots", style="bold red"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=36, style="red", complete_style="bright_red"),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )


# ─────────────────────────────────────────────
#  Per-attempt logging
# ─────────────────────────────────────────────

def log_attempt(
    attempt_num: int,
    payload_id: str,
    score: int,
    detection: str,
    is_mutation: bool = False,
    strategy: str | None = None,
    duration_ms: int = 0,
) -> None:
    """Print a single-line attempt result with colour-coded score."""
    det_col   = detection_color(detection)
    sc_col    = score_color(score)
    prefix    = "[bold cyan][MUT][/bold cyan]" if is_mutation else "[bold blue][ATT][/bold blue]"
    strat_str = f" via [bold]{strategy}[/bold]" if strategy else ""
    time_str  = f" [{duration_ms}ms]" if duration_ms else ""

    line = (
        f"{prefix} #{attempt_num:03d} [{payload_id}]{strat_str}{time_str} · "
        f"[{det_col}]{detection.upper().replace('_', ' ')}[/{det_col}] · "
        f"Score: [{sc_col}][bold]{score}/100[/bold][/{sc_col}]"
    )

    if score >= 75:
        console.print(f"[bold bright_red][!JAILBREAK][/bold bright_red] {line}")
    elif score >= 50:
        console.print(f"[bold yellow][ BYPASS  ][/bold yellow] {line}")
    elif score == 0:
        console.print(f"[dim][ BLOCKED ][/dim] {line}")
    else:
        console.print(f"[dim][ INFO    ][/dim] {line}")


def log_mutation(strategy: str, reason: str) -> None:
    """Print a mutation strategy selection notice."""
    console.print(
        f"  [bold cyan]↳ Mutation[/bold cyan] → "
        f"[cyan]{strategy}[/cyan]  "
        f"[dim]{reason[:90]}[/dim]"
    )


# ─────────────────────────────────────────────
#  Generic log helpers
# ─────────────────────────────────────────────

def log_info(msg: str) -> None:
    console.print(f"[bold green][+][/bold green] {msg}")


def log_warn(msg: str) -> None:
    console.print(f"[bold yellow][!][/bold yellow] {msg}")


def log_error(msg: str) -> None:
    console.print(f"[bold red][✗][/bold red] {msg}")


def log_success(msg: str) -> None:
    console.print(f"[bold bright_green][✓][/bold bright_green] {msg}")


def log_debug(msg: str) -> None:
    console.print(f"[dim][DBG] {msg}[/dim]")


# ─────────────────────────────────────────────
#  Startup diagnostics panel
# ─────────────────────────────────────────────

def print_diagnostics(
    provider_name: str,
    model: str,
    subject: str,
    mode: str,
    payload_count: int,
    connection_ok: bool,
    connection_msg: str,
) -> None:
    """Print a pre-run configuration and connectivity summary."""
    status_str = (
        "[bold bright_green]✓ Connected[/bold bright_green]"
        if connection_ok
        else "[bold red]✗ FAILED[/bold red]"
    )
    content = (
        f"  Provider   : [bold]{provider_name}[/bold]\n"
        f"  Model      : [bold]{model}[/bold]\n"
        f"  Subject    : [italic]{subject}[/italic]\n"
        f"  Mode       : [bold]{mode.upper()}[/bold]\n"
        f"  Payloads   : [bold]{payload_count}[/bold] loaded\n"
        f"  Connection : {status_str}  [dim]{connection_msg}[/dim]"
    )
    console.print(
        Panel(
            content,
            title="[bold red]JailHunter — Run Configuration[/bold red]",
            border_style="red",
            padding=(0, 2),
        )
    )
    console.print()


# ─────────────────────────────────────────────
#  Final summary
# ─────────────────────────────────────────────

def print_summary(summary: object) -> None:
    """
    Render a full terminal summary table after a run completes.
    Accepts a RunSummary object (typed as object to avoid circular import).
    """
    console.print()
    interrupted = getattr(summary, "interrupted", False)
    title = (
        "[bold yellow]PARTIAL RESULTS — RUN INTERRUPTED[/bold yellow]"
        if interrupted
        else "[bold red]JAILHUNTER RESULTS[/bold red]"
    )
    console.print(Rule(title, style="red"))
    console.print()

    # ── Stats table ────────────────────────────────────────────────────────
    stats = Table(
        title="Run Statistics",
        box=box.ROUNDED,
        border_style="red",
        header_style="bold red",
        show_header=True,
    )
    stats.add_column("Metric",  style="bold white", width=32)
    stats.add_column("Value",   style="cyan",        width=22)

    hs = summary.highest_score  # type: ignore[attr-defined]
    sc = score_color(hs)

    stats.add_row("Provider / Model",  f"{summary.target_provider} / {summary.target_model}")  # type: ignore
    stats.add_row("Mode",              summary.mode.value.upper())  # type: ignore
    stats.add_row("Subject",           summary.subject[:50])  # type: ignore
    stats.add_row("Duration",          f"{summary.duration_seconds}s")  # type: ignore
    stats.add_row("Payloads Tested",   str(summary.total_payloads))  # type: ignore
    stats.add_row("Total Attempts",    str(summary.total_attempts))  # type: ignore
    stats.add_row("", "")

    stats.add_row(
        "[bold bright_green]Jailbreaks (≥75)[/bold bright_green]",
        f"[bold bright_green]{summary.successful_jailbreaks}[/bold bright_green]",  # type: ignore
    )
    stats.add_row(
        "[bold yellow]Partial Bypasses (50–74)[/bold yellow]",
        f"[bold yellow]{summary.partial_bypasses}[/bold yellow]",  # type: ignore
    )
    stats.add_row(
        "[bold red]Refusals (<25)[/bold red]",
        f"[bold red]{summary.refusals}[/bold red]",  # type: ignore
    )
    stats.add_row(
        "[bold magenta]Prompt Leakages[/bold magenta]",
        f"[bold magenta]{summary.prompt_leakages}[/bold magenta]",  # type: ignore
    )
    stats.add_row("", "")
    stats.add_row(
        "Highest Score",
        f"[{sc}][bold]{hs}/100[/bold][/{sc}]",
    )
    stats.add_row(
        "Success Rate",
        f"[bold]{summary.success_rate}%[/bold]",  # type: ignore
    )

    console.print(stats)
    console.print()

    # ── Best finding panel ─────────────────────────────────────────────────
    if summary.best_payload:  # type: ignore
        console.print(
            Panel(
                f"[bold yellow]PAYLOAD:[/bold yellow]\n"
                f"[white]{summary.best_payload[:500]}[/white]\n\n"  # type: ignore
                f"[bold green]RESPONSE SNIPPET:[/bold green]\n"
                f"[dim]{(summary.best_response or '')[:600]}[/dim]",  # type: ignore
                title=f"[bold bright_red]Best Finding · Score {hs}/100[/bold bright_red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        console.print()

    # ── Per-payload breakdown ──────────────────────────────────────────────
    breakdown = Table(
        title="Payload Breakdown",
        box=box.SIMPLE_HEAD,
        border_style="dim",
        header_style="bold",
    )
    breakdown.add_column("ID",          width=8)
    breakdown.add_column("Category",    width=22)
    breakdown.add_column("Attempts",    width=9,  justify="center")
    breakdown.add_column("Best Score",  width=11, justify="center")
    breakdown.add_column("Detection",   width=24)

    sorted_results = sorted(
        summary.all_results,  # type: ignore
        key=lambda r: -r.best_score,
    )
    for r in sorted_results:
        det = (
            r.best_attempt.analysis.detection_type.value
            if r.best_attempt
            else "—"
        )
        det_col = detection_color(det)
        sc_col  = score_color(r.best_score)

        breakdown.add_row(
            r.payload_id,
            r.category.replace("_", " "),
            str(len(r.attempts)),
            f"[{sc_col}][bold]{r.best_score}[/bold][/{sc_col}]",
            f"[{det_col}]{det.replace('_', ' ')}[/{det_col}]",
        )

    console.print(breakdown)
    console.print()
