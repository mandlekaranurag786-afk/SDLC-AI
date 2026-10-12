import re

STOPWORDS = {
    "we", "are", "the", "a", "an", "our", "organizations", "organization",
    "company", "i", "you", "they", "my", "is", "need", "want", "require",
    "build", "create", "develop"
}

def format_title_preserve_acronyms(text: str) -> str:
    """Capitalizes words while preserving uppercase acronyms like HR, SDLC, API, AI, QA, etc."""
    words = text.split()
    formatted = []
    for w in words:
        clean_w = w.strip(" .,;:!?\"'()")
        if clean_w.isupper() and len(clean_w) > 1:
            formatted.append(clean_w)
        else:
            formatted.append(clean_w.capitalize())
    return " ".join(formatted)


def clean_and_validate_project_name(candidate: str | None) -> str | None:
    """
    Validates candidate project name string:
    - Strips whitespace & punctuation
    - Returns None if empty or starts with stopword
    - Returns formatted title case string max 6 words
    """
    if not candidate or not isinstance(candidate, str):
        return None

    cleaned = candidate.strip()
    words = cleaned.split()
    if not words:
        return None

    first_word_lower = words[0].lower().strip(".,;:!?\"'()")
    if first_word_lower in STOPWORDS:
        return None

    # Keep at most 6 words
    title_words = words[:6]
    title_str = " ".join(title_words).strip(" .,;:!?\"'()")
    if not title_str or len(title_str) < 3:
        return None

    return format_title_preserve_acronyms(title_str)


def resolve_project_name(
    user_provided_name: str | None = None,
    extracted_name: str | None = None,
    problem_statement: str = ""
) -> str:
    """
    Resolves project name using explicit hierarchy:
    1. user_provided_name (if non-empty and valid)
    2. extracted_name (from LLM requirement analysis)
    3. Heuristic clean title
    4. Fallback: "Untitled Project"
    """
    # 1. User provided name
    if user_provided_name and user_provided_name.strip():
        valid_user = clean_and_validate_project_name(user_provided_name)
        if valid_user:
            return valid_user
        return format_title_preserve_acronyms(user_provided_name.strip())

    # 2. Extracted LLM name
    if extracted_name:
        valid_extracted = clean_and_validate_project_name(extracted_name)
        if valid_extracted:
            return valid_extracted

    # 3. Heuristic extraction from problem statement
    if problem_statement:
        raw_words = [w.strip(".,;:!?\"'()") for w in problem_statement.split() if w.strip()]
        valid_words = [w for w in raw_words if w.lower() not in STOPWORDS and len(w) > 2]
        if valid_words:
            candidate = " ".join(valid_words[:4])
            valid_cand = clean_and_validate_project_name(candidate)
            if valid_cand:
                return valid_cand

    # 4. Fallback
    return "Untitled Project"
