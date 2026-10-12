import os
import shutil
from pathlib import Path
import pytest
from integration_utils import log_prompt_debug

@pytest.fixture(autouse=True)
def cleanup_logs():
    if Path("logs").exists():
        shutil.rmtree("logs", ignore_errors=True)
    yield
    if Path("logs").exists():
        shutil.rmtree("logs", ignore_errors=True)

def test_prompt_logging_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_PROMPT_LOGGING", raising=False)
    log_prompt_debug("TEST_STAGE", "Problem statement: Secrets and text here.")
    assert not Path("logs/prompts_debug.log").exists()


def test_prompt_logging_enabled_redacted(monkeypatch):
    monkeypatch.setenv("ENABLE_PROMPT_LOGGING", "true")
    monkeypatch.setenv("ENABLE_DEBUG_LOGGING", "false")
    log_prompt_debug("TEST_STAGE", "Problem statement: Secret onboarding details here.")
    
    assert Path("logs/prompts_debug.log").exists()
    content = Path("logs/prompts_debug.log").read_text(encoding="utf-8")
    assert "REDACTED" in content
    assert "Secret onboarding details" not in content


def test_prompt_logging_enabled_debug(monkeypatch):
    monkeypatch.setenv("ENABLE_PROMPT_LOGGING", "true")
    monkeypatch.setenv("ENABLE_DEBUG_LOGGING", "true")
    log_prompt_debug("TEST_STAGE", "Problem statement: Secret onboarding details here.")
    
    assert Path("logs/prompts_debug.log").exists()
    content = Path("logs/prompts_debug.log").read_text(encoding="utf-8")
    assert "Secret onboarding details" in content
