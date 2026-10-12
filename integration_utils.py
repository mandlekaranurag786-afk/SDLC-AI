import os
import re
from pathlib import Path
from typing import Any

ALIAS_MAP = {
    "sap successfactors": ["sap", "successfactors", "success factors", "hrms"],
    "ms active directory": ["active directory", "ad", "azure ad", "sso", "identity"],
    "ms teams": ["teams", "microsoft teams", "teams bot"],
    "docusign": ["docusign", "e-signature", "esignature", "docu sign"],
    "servicenow": ["servicenow", "service now", "it asset ticket"],
    "hrms": ["hrms", "human resource management system", "employee data sync"],
    "email workflow": ["email", "automated email", "email notifications"],
    "slack": ["slack", "slack support", "slack channel"]
}

def log_prompt_debug(stage: str, prompt: str):
    """
    Log prompts to logs/prompts_debug.log IF ENABLE_PROMPT_LOGGING=true.
    If ENABLE_DEBUG_LOGGING is false, redact raw problem statements for privacy.
    """
    enable_prompt_logging = os.getenv("ENABLE_PROMPT_LOGGING", "false").lower() == "true"
    if not enable_prompt_logging:
        return

    enable_debug = os.getenv("ENABLE_DEBUG_LOGGING", "false").lower() == "true"

    logged_prompt = prompt
    if not enable_debug:
        # Redact raw problem statement / user inputs if debug flag is off
        logged_prompt = re.sub(
            r"(Problem Statement:?[\s\n]+)([^\n]+)",
            r"\1[REDACTED — set ENABLE_DEBUG_LOGGING=true to view]",
            logged_prompt,
            flags=re.IGNORECASE
        )

    try:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "prompts_debug.log", "a", encoding="utf-8") as f:
            f.write(f"=== {stage} PROMPT ===\n{logged_prompt}\n\n")
    except Exception as e:
        print(f"[WARNING] Could not write prompt log: {e}")


def extract_structured_list(value: Any) -> list[str]:
    """Extract a clean list of item strings from text, list, or dict structures."""
    if not value:
        return []
    if isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, str):
                items.extend([s.strip() for s in re.split(r"[,;\n•\-]", item) if s.strip()])
            elif isinstance(item, dict):
                v = item.get("value") or item.get("name") or item.get("item")
                if v:
                    items.extend(extract_structured_list(v))
        return list(dict.fromkeys(items))
    if isinstance(value, str):
        parts = [s.strip(" .:-*•") for s in re.split(r"[,;\n•]", value) if s.strip(" .:-*•")]
        return list(dict.fromkeys(parts))
    return []


def check_items_coverage(doc_text: str, items: list[str]) -> tuple[list[str], list[str]]:
    """
    Checks if each required item (or its aliases) appears in doc_text (case-insensitive).
    Returns (present_items, missing_items).
    """
    if not items or not doc_text:
        return ([], items or [])

    doc_lower = doc_text.lower()
    present = []
    missing = []

    for item in items:
        item_clean = item.strip()
        item_lower = item_clean.lower()

        # Check exact string
        if item_lower in doc_lower:
            present.append(item_clean)
            continue

        # Check alias matches
        aliases = []
        for key, alias_list in ALIAS_MAP.items():
            if key in item_lower or item_lower in key:
                aliases.extend(alias_list)

        found_alias = any(alias in doc_lower for alias in aliases)
        if found_alias:
            present.append(item_clean)
        else:
            missing.append(item_clean)

    return (present, missing)
