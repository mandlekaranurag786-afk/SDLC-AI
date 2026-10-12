"""
feature_flags.py

Centralized feature flags for deterministic improvements to document generation.
Per architecture requirements:
- Flags default to ON (True)
- Located in feature_flags.py (never a root config.py, to avoid shadowing streamlit_app/config.py)
"""

ENABLE_STORY_ID_RENUMBERING = True
ENABLE_STORY_FR_LINKING = True
ENABLE_ESTIMATION_FR_ALIGNMENT = True
ENABLE_TITLE_SANITY = True
ENABLE_PROVENANCE_TAG_FILTERING = True
ENABLE_VALIDATOR_FP_FIXES = True
ENABLE_CLEAN_OPEN_ITEMS = True
ENABLE_ISOLATE_VALIDATOR_OPEN_ITEMS = True
ENABLE_METRIC_ALIGNMENT = True
