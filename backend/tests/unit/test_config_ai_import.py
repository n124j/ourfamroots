"""Unit tests for the AI-import-related Settings fields."""
from __future__ import annotations

from src.config import Settings


def test_ai_import_settings_have_sane_defaults(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 32)
    settings = Settings()
    assert settings.anthropic_api_key == ""
    assert settings.ai_import_model == "claude-sonnet-5"
    assert settings.ai_import_max_screenshot_bytes == 15 * 1024 * 1024
