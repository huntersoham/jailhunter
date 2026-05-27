"""
JailHunter Configuration
Centralised settings with .env support, environment variable overrides,
and typed defaults. Import `settings` anywhere in the codebase.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Load .env from project root if it exists (must happen before any os.getenv calls)
try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=_env_file, override=False)  # won't clobber real env vars
except ImportError:
    pass  # python-dotenv optional; fall back to real env vars only


@dataclass
class JailHunterSettings:
    """
    All runtime configuration for JailHunter.
    Values are read from environment variables (or .env) at import time.
    Override individual fields after import for testing.
    """

    # ── OpenAI / compatible API ──────────────────────────────────────────────
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    openai_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

    # ── Ollama ───────────────────────────────────────────────────────────────
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )

    # ── Request behaviour ────────────────────────────────────────────────────
    request_timeout: int = field(
        default_factory=lambda: int(os.getenv("JH_TIMEOUT", "60"))
    )
    max_concurrent: int = field(
        default_factory=lambda: int(os.getenv("JH_CONCURRENT", "3"))
    )
    request_delay: float = field(
        default_factory=lambda: float(os.getenv("JH_DELAY", "0.5"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("JH_RETRIES", "3"))
    )
    retry_base_delay: float = field(
        default_factory=lambda: float(os.getenv("JH_RETRY_BASE", "1.0"))
    )

    # ── Scoring ──────────────────────────────────────────────────────────────
    success_threshold: int = field(
        default_factory=lambda: int(os.getenv("JH_THRESHOLD", "75"))
    )

    # ── Reports ──────────────────────────────────────────────────────────────
    report_dir: str = field(
        default_factory=lambda: os.getenv("JH_REPORT_DIR", "./jh_reports")
    )

    # ── Debug ────────────────────────────────────────────────────────────────
    debug: bool = field(
        default_factory=lambda: os.getenv("JH_DEBUG", "").lower() in ("1", "true", "yes")
    )
    verbose: bool = field(
        default_factory=lambda: os.getenv("JH_VERBOSE", "").lower() in ("1", "true", "yes")
    )


# Singleton — import this everywhere
settings = JailHunterSettings()
