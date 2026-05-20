"""
JailHunter Configuration
Handles defaults, environment variables, and runtime config.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # Provider settings
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))

    # Request settings
    request_timeout: int = 60
    max_concurrent:  int = 3
    request_delay:   float = 0.5  # seconds between requests

    # Scoring
    success_threshold: int = 75

    # Reports
    report_dir: str = "./reports"

    # Logging
    verbose: bool = False


# Global config instance
config = Config()
